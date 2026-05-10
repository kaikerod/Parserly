## 🇧🇷 Português

O **Parserly** é um analisador de currículos focado em compatibilidade com ATS (*Applicant Tracking Systems*). O sistema extrai texto de arquivos PDF ou DOCX, processa o conteúdo via IA e gera um diagnóstico detalhado para ajudar candidatos a superarem filtros automáticos.

### ✨ Funcionalidades

- 📁 **Upload Versátil**: Suporte para arquivos PDF e DOCX.
- 📊 **Score ATS**: Pontuação de 0 a 100 baseada em critérios reais de recrutamento.
- 💡 **Sugestões Práticas**: Recomendações específicas para melhorar o conteúdo e formatação.
- 🔐 **Magic Link**: Login simplificado e seguro via e-mail.
- 💳 **Paywall Integrado**: Integração com Mercado Pago para análise de créditos extras.
- 🕒 **Persistência de análises**: As análises ficam salvas para acesso rápido ao histórico e consultas posteriores.

### 🛠️ Stack Tecnológica

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Next.js](https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/tailwindcss-%2338B2AC.svg?style=for-the-badge&logo=tailwind-css&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

### 🚀 Como Rodar Localmente

#### Requisitos
- Node.js 18+
- Python 3.12+
- Docker & Docker Compose

#### Opção 1: Docker Compose (Recomendado)
```bash
# 1. Configure as variáveis de ambiente
cp .env.example .env

# 2. Suba a stack completa
docker compose up --build
```
Acesse em: `http://localhost:3000`

#### Opção 2: Desenvolvimento Separado
**Frontend:**
```bash
cd frontend && npm install && npm run dev
```
**Backend:**
```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# Unix:
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 🔑 Variáveis de Ambiente
As variáveis essenciais estão no arquivo `.env.example`. Não esqueça de configurar:
- `OPENROUTER_API_KEY` (Para a IA)
- `RESEND_API_KEY` (Para os e-mails)
- `API_PUBLIC_URL` (URL pública da API usada nos webhooks)
- `MERCADOPAGO_ACCESS_TOKEN` (Para pagamentos)
- `MERCADOPAGO_WEBHOOK_SECRET` (Para validação de webhooks)

### Operacao de Banco em Producao

O backend nao cria nem atualiza schema automaticamente quando `ENVIRONMENT=production` ou `VERCEL=1`. Antes de promover uma versao para producao, execute obrigatoriamente as migrations:

```bash
cd backend
DATABASE_URL="$PRODUCTION_DATABASE_URL" python -m alembic upgrade head
```

O workflow `.github/workflows/vercel-promote.yml` executa esta etapa antes do `vercel promote` e falha se `PRODUCTION_DATABASE_URL` nao estiver configurada. Nao mova migrations para startup/runtime da API: isso pode gerar corrida entre instancias e deixar deploys parcialmente saudaveis.

O endpoint `/api/v1/health` tambem valida a revisao esperada do Alembic e colunas essenciais. Se o banco estiver conectado mas o schema estiver ausente ou desatualizado, o health retorna `503` com status `degraded`.

---

## 🇺🇸 English

**Parserly** is a resume analyzer focused on ATS (*Applicant Tracking Systems*) compatibility. The system extracts text from PDF or DOCX files, processes the content via AI, and generates a detailed diagnosis to help candidates overcome automated filters.

### ✨ Features

- 📁 **Versatile Upload**: Support for PDF and DOCX files.
- 📊 **ATS Score**: 0 to 100 score based on real recruitment criteria.
- 💡 **Practical Suggestions**: Specific recommendations to improve content and formatting.
- 🔐 **Magic Link**: Simplified and secure login via email.
- 💳 **Integrated Paywall**: Integration with Mercado Pago for extra credit analysis.
- 🕒 **Analysis persistence**: Analyses are saved for quick access to history and later review.

### 🛠️ Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy async, Alembic.
- **Frontend**: Next.js 14 (App Router), Tailwind CSS.
- **Database**: PostgreSQL 16 & Redis (Cache/Queue).
- **Services**: OpenRouter (AI), Resend (Email), Mercado Pago (Payments).

### 🚀 Getting Started

#### Requirements
- Node.js 18+
- Python 3.12+
- Docker & Docker Compose

#### Option 1: Docker Compose (Recommended)
```bash
# 1. Setup environment variables
cp .env.example .env

# 2. Spin up the stack
docker compose up --build
```
Access at: `http://localhost:3000`

#### Option 2: Manual Setup
**Frontend:**
```bash
cd frontend && npm install && npm run dev
```
**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate # or .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 🔑 Environment Variables
Key variables are listed in `.env.example`. Essential configurations:
- `OPENROUTER_API_KEY` (For AI)
- `RESEND_API_KEY` (For Emails)
- `API_PUBLIC_URL` (Public API URL used by webhooks)
- `MERCADOPAGO_ACCESS_TOKEN` (For Payments)
- `MERCADOPAGO_WEBHOOK_SECRET` (For webhook validation)

### Production Database Operations

The backend does not create or update schema automatically when `ENVIRONMENT=production` or `VERCEL=1`. Before promoting a release to production, migrations must be run:

```bash
cd backend
DATABASE_URL="$PRODUCTION_DATABASE_URL" python -m alembic upgrade head
```

The `.github/workflows/vercel-promote.yml` workflow runs this before `vercel promote` and fails when `PRODUCTION_DATABASE_URL` is missing. Do not run migrations from API startup/runtime, because concurrent instances can race and leave a deployment partially healthy.

The `/api/v1/health` endpoint also validates the expected Alembic revision and essential columns. If the database is reachable but the schema is missing or outdated, health returns `503` with `degraded` status.

---

## 📄 Licença / License

Este repositório utiliza a [Business Source License 1.1](./LICENSE).
This repository uses the [Business Source License 1.1](./LICENSE).
