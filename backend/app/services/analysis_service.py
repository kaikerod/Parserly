from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile, gettempdir
from uuid import UUID

import httpx
import pdfplumber
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.quotas import FREE_ANALYSIS_LIMIT
from app.models.analysis import Analysis
from app.models.user import User
from app.schemas.analysis import AnalysisReport

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MIN_RESUME_CHARS = 100
MAX_AI_ATTEMPTS = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
OPENROUTER_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)
MIN_RESUME_WORDS = 40
MIN_ALPHA_RATIO = 0.45
MAX_RAW_PDF_MARKERS = 3
MIN_RAW_PDF_TECHNICAL_TOKENS = 8
MAX_RAW_PDF_TOKEN_RATIO = 0.08
WORD_RE = re.compile(r"[^\W\d_]{2,}(?:[-'][^\W\d_]{2,})?")
PDF_TECHNICAL_TOKEN_RE = re.compile(
    r"\b(?:"
    r"obj|endobj|stream|endstream|xref|startxref|trailer|"
    r"flatedecode|decodeparms|mediabox|procset|xobject|"
    r"catalog|pages|metadata|font|contents|resources"
    r")\b",
    re.IGNORECASE,
)
PDF_OBJECT_MARKER_RE = re.compile(
    r"\b\d+\s+\d+\s+obj\b|"
    r"\bendobj\b|"
    r"\bstream\b|"
    r"\bendstream\b|"
    r"\bxref\b|"
    r"\bstartxref\b|"
    r"/(?:Type|Catalog|Pages|Font|Contents|Resources|Length|Filter)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """
Voce e um avaliador senior de curriculos para ATS (Applicant Tracking Systems).
Analise apenas o texto do curriculo enviado pelo usuario e produza um diagnostico
tecnico, pratico e conservador em portugues do Brasil.

Responda exclusivamente com um objeto JSON valido, sem markdown, sem comentarios,
sem texto antes ou depois do JSON. A resposta deve comecar com "{" e terminar
com "}". Use exatamente estas chaves e nao adicione campos extras:

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

Criterios de avaliacao:
- keywords: aderencia a palavras-chave, ferramentas, cargos, senioridade,
  certificacoes e termos comuns para a funcao detectada.
- formatting: compatibilidade com parsers ATS, legibilidade, ausencia de tabelas
  complexas, colunas confusas, imagens, icones ou elementos que prejudiquem a leitura.
- structure: organizacao das secoes, ordem das informacoes, clareza de experiencia,
  formacao, competencias e consistencia cronologica.
- contact_info: presenca e clareza de email, telefone, localizacao, portfolio,
  LinkedIn ou outros canais profissionais quando aplicavel.
- quantifiable_achievements: uso de resultados mensuraveis, numeros, impacto,
  escopo, tecnologias e evidencias concretas de contribuicao.

Regras obrigatorias:
- Calcule "overall_score" como media ponderada arredondada das categorias:
  keywords 35%, formatting 20%, structure 20%, contact_info 10%,
  quantifiable_achievements 15%.
- Todos os scores devem ser inteiros entre 0 e 100.
- Cada feedback deve explicar a nota daquela categoria em uma frase objetiva.
- Ordene "recommendations" por prioridade: high, depois medium, depois low.
- Retorne de 1 a 7 recomendacoes; nunca retorne lista vazia.
- Cada recomendacao deve ser acionavel e especifica ao curriculo analisado.
- "detected_role" deve ser o cargo principal inferido; use null se nao houver
  evidencia suficiente.
- Nao invente experiencias, cargos, empresas, formacoes, certificacoes ou metricas.
- Nao replique dados pessoais sensiveis do curriculo no feedback.
- Se o texto nao parecer um curriculo reconhecivel, retorne overall_score 0,
  scores 0 em todas as categorias, detected_role null e uma unica recomendacao
  de prioridade high explicando que o arquivo precisa conter um curriculo legivel.
""".strip()

STRICT_JSON_RETRY_SUFFIX = (
    "\n\nATENCAO: Sua resposta anterior nao era JSON valido. "
    "Retorne APENAS o objeto JSON, sem markdown, comentarios ou texto adicional."
)

ANALYSIS_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["overall_score", "categories", "recommendations", "detected_role"],
    "properties": {
        "overall_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
        },
        "categories": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "keywords",
                "formatting",
                "structure",
                "contact_info",
                "quantifiable_achievements",
            ],
            "properties": {
                "keywords": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["score", "feedback"],
                    "properties": {
                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "feedback": {"type": "string", "minLength": 1},
                    },
                },
                "formatting": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["score", "feedback"],
                    "properties": {
                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "feedback": {"type": "string", "minLength": 1},
                    },
                },
                "structure": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["score", "feedback"],
                    "properties": {
                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "feedback": {"type": "string", "minLength": 1},
                    },
                },
                "contact_info": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["score", "feedback"],
                    "properties": {
                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "feedback": {"type": "string", "minLength": 1},
                    },
                },
                "quantifiable_achievements": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["score", "feedback"],
                    "properties": {
                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "feedback": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
        "recommendations": {
            "type": "array",
            "minItems": 1,
            "maxItems": 7,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["priority", "action", "expected_impact"],
                "properties": {
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "action": {"type": "string", "minLength": 1},
                    "expected_impact": {"type": "string", "minLength": 1},
                },
            },
        },
        "detected_role": {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ],
        },
    },
}


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


@dataclass(frozen=True, slots=True)
class ExtractedResumeText:
    text: str
    file_type: str
    extraction_method: str
    pages_processed: int | None


@dataclass(frozen=True, slots=True)
class ExtractedTextQuality:
    characters: int
    words: int
    alpha_ratio: float
    pdf_technical_tokens: int
    pdf_object_markers: int


class AnalysisService:
    def __init__(self, db_session: AsyncSession, settings: Settings) -> None:
        self.db_session = db_session
        self.settings = settings

    async def analyze_resume(
        self,
        user: User | None,
        upload_file: UploadFile,
        *,
        guest_analyses_used: int | None = None,
    ) -> PersistedAnalysisResult:
        if user is not None:
            await self.db_session.refresh(user)
            if user.analyses_used >= FREE_ANALYSIS_LIMIT:
                raise QuotaExceeded

        temp_path: Path | None = None
        try:
            temp_path = await self._write_upload_to_temp_file(upload_file)
            extracted_resume = await self._extract_text(temp_path, upload_file.filename or "")
            quality = self._validate_extracted_text_quality(
                extracted_resume.text,
                file_type=extracted_resume.file_type,
                extraction_method=extracted_resume.extraction_method,
                pages_processed=extracted_resume.pages_processed,
            )
            self._log_extraction_accepted(extracted_resume, quality)

            ai_result = await self._analyze_with_openrouter(extracted_resume.text)
            return await self._persist_analysis(
                user=user,
                filename=upload_file.filename or "resume",
                ai_result=ai_result,
                guest_analyses_used=guest_analyses_used,
            )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    async def _write_upload_to_temp_file(self, upload_file: UploadFile) -> Path:
        filename = upload_file.filename or ""
        suffix = Path(filename).suffix.lower()
        file_type = self._safe_file_type_from_suffix(suffix)
        if suffix not in ALLOWED_EXTENSIONS:
            self._log_file_rejected(
                file_type=file_type,
                extraction_method="not_started",
                reason="unsupported_type",
            )
            raise InvalidResumeFile("unsupported_type")

        total_bytes = 0
        temp_dir = self._upload_temp_dir()
        with NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as temp_file:
            temp_path = Path(temp_file.name)
            while chunk := await upload_file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    temp_file.close()
                    temp_path.unlink(missing_ok=True)
                    self._log_file_rejected(
                        file_type=file_type,
                        extraction_method="not_started",
                        reason="file_too_large",
                    )
                    raise InvalidResumeFile("file_too_large")
                temp_file.write(chunk)

        if total_bytes == 0:
            temp_path.unlink(missing_ok=True)
            self._log_file_rejected(
                file_type=file_type,
                extraction_method="not_started",
                reason="insufficient_content",
            )
            raise InvalidResumeFile("insufficient_content")

        return temp_path

    def _upload_temp_dir(self) -> Path:
        temp_dir = Path(self.settings.upload_tmp_dir or gettempdir())
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    async def _extract_text(self, file_path: Path, filename: str) -> ExtractedResumeText:
        suffix = Path(filename).suffix.lower()
        file_type = self._safe_file_type_from_suffix(suffix)
        extraction_method = self._extraction_method_for_suffix(suffix)
        try:
            if suffix == ".pdf":
                text, pages_processed = await asyncio.to_thread(
                    self._extract_pdf_text,
                    file_path,
                )
                return ExtractedResumeText(
                    text=text,
                    file_type=file_type,
                    extraction_method=extraction_method,
                    pages_processed=pages_processed,
                )
            if suffix == ".docx":
                return ExtractedResumeText(
                    text=await asyncio.to_thread(self._extract_docx_text, file_path),
                    file_type=file_type,
                    extraction_method=extraction_method,
                    pages_processed=None,
                )
        except InvalidResumeFile as exc:
            self._log_file_rejected(
                file_type=file_type,
                extraction_method=extraction_method,
                reason=exc.reason,
            )
            raise
        except Exception as exc:
            self._log_file_rejected(
                file_type=file_type,
                extraction_method=extraction_method,
                reason="corrupted",
            )
            raise InvalidResumeFile("corrupted") from exc

        self._log_file_rejected(
            file_type=file_type,
            extraction_method=extraction_method,
            reason="unsupported_type",
        )
        raise InvalidResumeFile("unsupported_type")

    def _extract_pdf_text(self, file_path: Path) -> tuple[str, int]:
        with file_path.open("rb") as file:
            header = file.read(5)
        if header != b"%PDF-":
            raise InvalidResumeFile("corrupted")

        page_texts: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            pages_processed = len(pdf.pages)
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    page_texts.append(page_text)

        return self._normalize_extracted_text("\n\n".join(page_texts)), pages_processed

    def _extract_docx_text(self, file_path: Path) -> str:
        document = Document(file_path)
        blocks: list[str] = []

        for child in document.element.body.iterchildren():
            if child.tag.endswith("}p"):
                paragraph_text = Paragraph(child, document).text
                if paragraph_text.strip():
                    blocks.append(paragraph_text)
            elif child.tag.endswith("}tbl"):
                table_text = self._extract_docx_table_text(Table(child, document))
                if table_text.strip():
                    blocks.append(table_text)

        return self._normalize_extracted_text("\n\n".join(blocks))

    def _extract_docx_table_text(self, table: Table) -> str:
        rows: list[str] = []
        for row in table.rows:
            cells: list[str] = []
            for cell in row.cells:
                cell_text = self._normalize_extracted_text(
                    "\n".join(paragraph.text for paragraph in cell.paragraphs)
                )
                if cell_text:
                    cells.append(" / ".join(cell_text.splitlines()))
            if cells:
                rows.append(" | ".join(cells))
        return "\n".join(rows)

    @staticmethod
    def _normalize_extracted_text(raw_text: str) -> str:
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        lines: list[str] = []
        previous_blank = True

        for raw_line in text.split("\n"):
            printable_line = "".join(
                char if char.isprintable() or char == "\t" else " " for char in raw_line
            )
            line = " ".join(printable_line.split())
            if line:
                lines.append(line)
                previous_blank = False
                continue
            if not previous_blank and lines:
                lines.append("")
                previous_blank = True

        while lines and lines[-1] == "":
            lines.pop()

        return "\n".join(lines)

    def _validate_extracted_text_quality(
        self,
        resume_text: str,
        *,
        file_type: str,
        extraction_method: str,
        pages_processed: int | None,
    ) -> ExtractedTextQuality:
        quality = self._measure_extracted_text_quality(resume_text)
        rejection_reason = self._extracted_text_rejection_reason(quality)

        if rejection_reason is not None:
            self._log_text_rejected(
                file_type=file_type,
                extraction_method=extraction_method,
                pages_processed=pages_processed,
                quality=quality,
                reason=rejection_reason,
            )
            raise InvalidResumeFile(rejection_reason)

        return quality

    @staticmethod
    def _extracted_text_rejection_reason(quality: ExtractedTextQuality) -> str | None:
        if quality.characters < MIN_RESUME_CHARS or quality.words < MIN_RESUME_WORDS:
            return "insufficient_content"

        if quality.alpha_ratio < MIN_ALPHA_RATIO:
            return "unreadable_content"

        has_raw_pdf_markers = quality.pdf_object_markers >= MAX_RAW_PDF_MARKERS
        raw_pdf_token_ratio = quality.pdf_technical_tokens / max(quality.words, 1)
        has_raw_pdf_tokens = (
            quality.pdf_technical_tokens >= MIN_RAW_PDF_TECHNICAL_TOKENS
            and raw_pdf_token_ratio >= MAX_RAW_PDF_TOKEN_RATIO
        )
        if has_raw_pdf_markers or has_raw_pdf_tokens:
            return "raw_pdf_content"

        return None

    @staticmethod
    def _measure_extracted_text_quality(resume_text: str) -> ExtractedTextQuality:
        stripped_text = resume_text.strip()
        non_space_chars = [char for char in stripped_text if not char.isspace()]
        alpha_chars = sum(1 for char in non_space_chars if char.isalpha())
        alpha_ratio = alpha_chars / max(len(non_space_chars), 1)

        words = WORD_RE.findall(stripped_text)
        pdf_technical_tokens = PDF_TECHNICAL_TOKEN_RE.findall(stripped_text)
        pdf_object_markers = PDF_OBJECT_MARKER_RE.findall(stripped_text)

        return ExtractedTextQuality(
            characters=len(stripped_text),
            words=len(words),
            alpha_ratio=alpha_ratio,
            pdf_technical_tokens=len(pdf_technical_tokens),
            pdf_object_markers=len(pdf_object_markers),
        )

    @staticmethod
    def _safe_file_type_from_suffix(suffix: str) -> str:
        if suffix in ALLOWED_EXTENSIONS:
            return suffix
        if not suffix:
            return "missing_extension"
        return "unsupported_extension"

    @staticmethod
    def _extraction_method_for_suffix(suffix: str) -> str:
        if suffix == ".pdf":
            return "pdfplumber"
        if suffix == ".docx":
            return "python-docx"
        return "unsupported"

    @staticmethod
    def _log_extraction_accepted(
        extracted_resume: ExtractedResumeText,
        quality: ExtractedTextQuality,
    ) -> None:
        logger.info(
            "Resume extraction accepted: file_type=%s extraction_method=%s "
            "characters=%s words=%s pages_processed=%s",
            extracted_resume.file_type,
            extracted_resume.extraction_method,
            quality.characters,
            quality.words,
            extracted_resume.pages_processed,
        )

    @staticmethod
    def _log_text_rejected(
        *,
        file_type: str,
        extraction_method: str,
        pages_processed: int | None,
        quality: ExtractedTextQuality,
        reason: str,
    ) -> None:
        logger.warning(
            "Resume extraction rejected: file_type=%s extraction_method=%s "
            "characters=%s words=%s pages_processed=%s reason=%s",
            file_type,
            extraction_method,
            quality.characters,
            quality.words,
            pages_processed,
            reason,
        )

    @staticmethod
    def _log_file_rejected(
        *,
        file_type: str,
        extraction_method: str,
        reason: str,
    ) -> None:
        logger.warning(
            "Resume file rejected: file_type=%s extraction_method=%s reason=%s",
            file_type,
            extraction_method,
            reason,
        )

    async def _analyze_with_openrouter(self, resume_text: str) -> AIAnalysisResult:
        if not self.settings.openrouter_api_key:
            logger.error("OpenRouter API key is not configured")
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
                    logger.error(
                        "Invalid OpenRouter JSON response on attempt %s using model %s",
                        attempt,
                        model,
                    )
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    self._log_openrouter_request_error(exc, attempt, model)
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

    @staticmethod
    def _log_openrouter_request_error(exc: Exception, attempt: int, model: str) -> None:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            logger.warning(
                "OpenRouter request failed on attempt %s using model %s: status=%s error=%s",
                attempt,
                model,
                exc.response.status_code,
                AnalysisService._openrouter_error_summary(exc.response),
            )
            return

        logger.warning(
            "OpenRouter request failed on attempt %s using model %s: %s",
            attempt,
            model,
            exc.__class__.__name__,
        )

    @staticmethod
    def _openrouter_error_summary(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return "non_json_error_response"

        if not isinstance(payload, dict):
            return "unexpected_error_response"

        error = payload.get("error")
        if not isinstance(error, dict):
            return "missing_error_object"

        code = error.get("code", response.status_code)
        message = error.get("message", "unknown")
        metadata = error.get("metadata")
        provider_name = metadata.get("provider_name") if isinstance(metadata, dict) else None
        provider = f" provider={provider_name}" if provider_name else ""
        return f"code={code}{provider} message={str(message)[:240]}"

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
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ats_resume_analysis",
                    "strict": True,
                    "schema": ANALYSIS_RESPONSE_SCHEMA,
                },
            },
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
        user: User | None,
        filename: str,
        ai_result: AIAnalysisResult,
        guest_analyses_used: int | None,
    ) -> PersistedAnalysisResult:
        report_json = ai_result.report.model_dump(mode="json")
        analysis = Analysis(
            user_id=user.id if user is not None else None,
            filename=filename,
            score=ai_result.report.overall_score,
            report_json=report_json,
            model_used=ai_result.model_used,
        )
        self.db_session.add(analysis)

        if user is None:
            analyses_used = guest_analyses_used or 0
        else:
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
            analyses_used=max(0, analyses_used),
        )
