from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID
from zipfile import BadZipFile, ZipFile

import httpx
from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.analysis import Analysis
from app.models.user import User
from app.schemas.analysis import AnalysisReport

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
FREE_ANALYSIS_LIMIT = 3
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MIN_RESUME_CHARS = 100
MAX_AI_ATTEMPTS = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
OPENROUTER_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)

SYSTEM_PROMPT = """
Voce e um especialista em sistemas ATS (Applicant Tracking Systems) e otimizacao de curriculos.

Analise o curriculo fornecido e retorne exclusivamente um objeto JSON valido com a seguinte estrutura:

{
  "overall_score": <integer 0-100>,
  "categories": {
    "keywords": {
      "score": <integer 0-100>,
      "feedback": "<string>"
    },
    "formatting": {
      "score": <integer 0-100>,
      "feedback": "<string>"
    },
    "structure": {
      "score": <integer 0-100>,
      "feedback": "<string>"
    },
    "contact_info": {
      "score": <integer 0-100>,
      "feedback": "<string>"
    },
    "quantifiable_achievements": {
      "score": <integer 0-100>,
      "feedback": "<string>"
    }
  },
  "recommendations": [
    {
      "priority": <"high"|"medium"|"low">,
      "action": "<string>",
      "expected_impact": "<string>"
    }
  ],
  "detected_role": "<string ou null>"
}

Regras:
- Nao inclua markdown, texto livre ou explicacoes fora do JSON.
- O campo "overall_score" deve ser a media ponderada das categorias
  (keywords: 35%, formatting: 20%, structure: 20%, contact_info: 10%,
  quantifiable_achievements: 15%).
- Ordene "recommendations" da maior para menor prioridade.
- Limite "recommendations" a 7 itens.
- Se o texto nao for um curriculo reconhecivel, retorne overall_score: 0 e
  recommendations com uma unica entrada explicando o problema.
""".strip()

STRICT_JSON_RETRY_SUFFIX = (
    "\n\nATENCAO: Sua resposta anterior nao era JSON valido. "
    "Retorne APENAS o objeto JSON, sem markdown, comentarios ou texto adicional."
)


class QuotaExceeded(Exception):
    pass


class InvalidResumeFile(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class AIAnalysisUnavailable(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AIAnalysisResult:
    report: AnalysisReport
    model_used: str


@dataclass(frozen=True, slots=True)
class PersistedAnalysisResult:
    id: UUID
    filename: str
    score: int
    report: AnalysisReport
    model_used: str
    created_at: datetime
    analyses_used: int


class AnalysisService:
    def __init__(self, db_session: AsyncSession, settings: Settings) -> None:
        self.db_session = db_session
        self.settings = settings

    async def analyze_resume(
        self,
        user: User,
        upload_file: UploadFile,
    ) -> PersistedAnalysisResult:
        await self.db_session.refresh(user)
        if user.analyses_used >= FREE_ANALYSIS_LIMIT:
            raise QuotaExceeded

        temp_path: Path | None = None
        try:
            temp_path = await self._write_upload_to_temp_file(upload_file)
            resume_text = await self._extract_text(temp_path, upload_file.filename or "")
            if len(resume_text.strip()) < MIN_RESUME_CHARS:
                raise InvalidResumeFile("insufficient_content")

            ai_result = await self._analyze_with_openrouter(resume_text)
            return await self._persist_analysis(
                user=user,
                filename=upload_file.filename or "resume",
                ai_result=ai_result,
            )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    async def _write_upload_to_temp_file(self, upload_file: UploadFile) -> Path:
        filename = upload_file.filename or ""
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise InvalidResumeFile("unsupported_type")

        total_bytes = 0
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            while chunk := await upload_file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    temp_file.close()
                    temp_path.unlink(missing_ok=True)
                    raise InvalidResumeFile("file_too_large")
                temp_file.write(chunk)

        if total_bytes == 0:
            temp_path.unlink(missing_ok=True)
            raise InvalidResumeFile("insufficient_content")

        return temp_path

    async def _extract_text(self, file_path: Path, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        try:
            if suffix == ".pdf":
                return await asyncio.to_thread(self._extract_pdf_text_placeholder, file_path)
            if suffix == ".docx":
                return await asyncio.to_thread(self._extract_docx_text_placeholder, file_path)
        except InvalidResumeFile:
            raise
        except Exception as exc:
            raise InvalidResumeFile("corrupted") from exc

        raise InvalidResumeFile("unsupported_type")

    def _extract_pdf_text_placeholder(self, file_path: Path) -> str:
        data = file_path.read_bytes()
        if not data.startswith(b"%PDF-"):
            raise InvalidResumeFile("corrupted")

        # Placeholder for pdfplumber extraction. This best-effort fallback keeps
        # the service flow testable until the real extractor is installed.
        decoded = data.decode("latin-1", errors="ignore")
        return self._normalize_extracted_text(decoded)

    def _extract_docx_text_placeholder(self, file_path: Path) -> str:
        # Placeholder for python-docx extraction using the DOCX zip/xml structure.
        try:
            with ZipFile(file_path) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
        except KeyError as exc:
            raise InvalidResumeFile("corrupted") from exc
        except BadZipFile as exc:
            raise InvalidResumeFile("corrupted") from exc

        text = (
            document_xml.replace("</w:t>", " ")
            .replace("</w:p>", "\n")
            .replace("<w:tab/>", " ")
        )
        return self._normalize_extracted_text(text)

    @staticmethod
    def _normalize_extracted_text(raw_text: str) -> str:
        chars = []
        inside_tag = False
        for char in raw_text:
            if char == "<":
                inside_tag = True
                chars.append(" ")
                continue
            if char == ">":
                inside_tag = False
                chars.append(" ")
                continue
            if inside_tag:
                continue
            if char.isprintable() or char in ("\n", "\t"):
                chars.append(char)
        return " ".join("".join(chars).split())

    async def _analyze_with_openrouter(self, resume_text: str) -> AIAnalysisResult:
        if not self.settings.openrouter_api_key:
            raise AIAnalysisUnavailable

        try:
            async with asyncio.timeout(90):
                return await self._run_openrouter_attempts(resume_text)
        except asyncio.TimeoutError as exc:
            logger.error("OpenRouter analysis timed out after retry budget")
            raise AIAnalysisUnavailable from exc

    async def _run_openrouter_attempts(self, resume_text: str) -> AIAnalysisResult:
        last_error: Exception | None = None
        strict_prompt = False

        async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
            for attempt in range(1, MAX_AI_ATTEMPTS + 1):
                model = self._model_for_attempt(attempt)
                try:
                    response = await client.post(
                        OPENROUTER_API_URL,
                        headers=self._openrouter_headers(),
                        json=self._openrouter_payload(
                            model=model,
                            resume_text=resume_text,
                            strict_prompt=strict_prompt,
                        ),
                    )
                    if response.status_code in RETRY_STATUS_CODES:
                        raise httpx.HTTPStatusError(
                            "OpenRouter returned retryable status",
                            request=response.request,
                            response=response,
                        )
                    response.raise_for_status()

                    report = self._parse_openrouter_response(response)
                    return AIAnalysisResult(report=report, model_used=model)
                except (
                    json.JSONDecodeError,
                    IndexError,
                    KeyError,
                    TypeError,
                    ValidationError,
                ) as exc:
                    strict_prompt = True
                    last_error = exc
                    logger.error("Invalid OpenRouter JSON response on attempt %s", attempt)
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                        if exc.response.status_code not in RETRY_STATUS_CODES:
                            break

                if attempt < MAX_AI_ATTEMPTS:
                    await asyncio.sleep(2 ** (attempt - 1))

        raise AIAnalysisUnavailable from last_error

    def _model_for_attempt(self, attempt: int) -> str:
        if attempt == 1:
            return self.settings.openrouter_model
        return self.settings.openrouter_fallback_model or self.settings.openrouter_model

    def _openrouter_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.app_url,
            "X-Title": "ATS Resume Analyzer",
        }

    @staticmethod
    def _openrouter_payload(
        model: str,
        resume_text: str,
        strict_prompt: bool,
    ) -> dict[str, object]:
        system_prompt = SYSTEM_PROMPT
        if strict_prompt:
            system_prompt += STRICT_JSON_RETRY_SUFFIX

        return {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": resume_text},
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }

    @staticmethod
    def _parse_openrouter_response(response: httpx.Response) -> AnalysisReport:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if isinstance(content, str):
            report_payload = json.loads(content)
        elif isinstance(content, dict):
            report_payload = content
        else:
            raise TypeError("OpenRouter content must be JSON text or object")

        return AnalysisReport.model_validate(report_payload)

    async def _persist_analysis(
        self,
        user: User,
        filename: str,
        ai_result: AIAnalysisResult,
    ) -> PersistedAnalysisResult:
        report_json = ai_result.report.model_dump(mode="json")
        analysis = Analysis(
            user_id=user.id,
            filename=filename,
            score=ai_result.report.overall_score,
            report_json=report_json,
            model_used=ai_result.model_used,
        )
        self.db_session.add(analysis)

        increment_result = await self.db_session.execute(
            update(User)
            .where(User.id == user.id, User.analyses_used < FREE_ANALYSIS_LIMIT)
            .values(
                analyses_used=User.analyses_used + 1,
                updated_at=func.now(),
            )
            .returning(User.analyses_used)
        )
        analyses_used = increment_result.scalar_one_or_none()
        if analyses_used is None:
            await self.db_session.rollback()
            raise QuotaExceeded

        try:
            await self.db_session.commit()
        except Exception:
            await self.db_session.rollback()
            raise

        await self.db_session.refresh(analysis)
        return PersistedAnalysisResult(
            id=analysis.id,
            filename=analysis.filename,
            score=analysis.score or 0,
            report=ai_result.report,
            model_used=analysis.model_used,
            created_at=analysis.created_at,
            analyses_used=analyses_used,
        )
