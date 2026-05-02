# Parserly

Parserly e um analisador de curriculos focado em compatibilidade com ATS (Applicant Tracking Systems). O produto recebe arquivos PDF ou DOCX, extrai o texto no backend, envia o conteudo para um modelo de IA via OpenRouter e retorna um relatorio com nota, diagnostico por categoria e recomendacoes praticas.

## Visao geral

- Upload de curriculo em PDF ou DOCX
- Analise ATS com pontuacao de 0 a 100
- Quota gratuita de 3 analises por visitante/usuario
- Identificacao por magic link por e-mail
- Paywall com checkout via AbacatePay quando a quota e esgotada
- Persistencia de analises e historico do usuario

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy async, Alembic
- Banco: PostgreSQL 16
- Cache e fila: Redis
- Frontend: Next.js 14, App Router, Tailwind CSS
- IA: OpenRouter
- E-mail: Resend
- Pagamento: AbacatePay
- Infra local: Docker Compose

## Estrutura

- `backend/` - API FastAPI e regras de negocio
- `frontend/` - interface Next.js
- `docs/` - documentacao complementar, quando necessario
- `tests/` - testes automatizados, quando adicionados
- `PRD.md` - documento de requisitos e arquitetura do produto

## Requisitos

- Node.js 18+ para o frontend
- Python 3.12+ para o backend
- Docker e Docker Compose para subir Postgres e Redis localmente

## Como rodar localmente

### Opcao 1: Docker Compose

1. Copie o arquivo de exemplo de ambiente e ajuste os valores:

```powershell
Copy-Item .env.example .env
```

2. Suba a stack completa:

```bash
docker compose up --build
```

3. Acesse:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Health check: `http://localhost:8000/health`

### Opcao 2: Rodando frontend e backend separadamente

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

#### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Variaveis de ambiente

As variaveis principais estao em `.env.example`. As mais importantes sao:

- `APP_URL`
- `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `RESEND_API_KEY`
- `EMAIL_FROM`
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `OPENROUTER_FALLBACK_MODEL`
- `ABACATEPAY_API_KEY`
- `ABACATEPAY_WEBHOOK_SECRET`
- `ANALYSIS_PRICE_CENTS`

## Scripts do frontend

No `frontend/package.json`:

- `npm run dev` - sobe o servidor de desenvolvimento
- `npm run build` - gera build de producao
- `npm run lint` - executa verificacao de tipos do TypeScript
- `npm run start` - inicia a aplicacao com build pronto

## Endpoints principais

- `POST /api/v1/auth/request-link`
- `GET /api/v1/auth/verify`
- `POST /api/v1/auth/logout`
- `POST /api/v1/analysis`
- `GET /api/v1/analysis`
- `GET /api/v1/analysis/{id}`
- `POST /api/v1/payments/create-charge`
- `POST /api/v1/payments/webhook`
- `GET /health`

## Documento de referencia

O escopo funcional, os fluxos e as regras de negocio detalhadas estao descritos em [`PRD.md`](./PRD.md).

## Licenca

Este repositorio usa a [Business Source License 1.1](./LICENSE).
