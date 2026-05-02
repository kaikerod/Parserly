# Fase 6 - Testes e Aceitacao

Status: concluida em 2026-05-02.

## Escopo Concluido

- Testes automatizados de backend adicionados em `backend/tests/`.
- Testes de superficie do frontend adicionados em `frontend/tests/deploy-acceptance.test.mjs`.
- Script de smoke pos-preview criado em `scripts/vercel-smoke.mjs`.
- Workflow `Vercel CI` atualizado para executar os testes de frontend e backend.
- Workflow `Promote Vercel Preview` atualizado para usar o mesmo smoke script antes de migrar e promover.

## Cobertura Backend

Os testes de backend cobrem os pontos de aceite da fase 6 sem chamadas reais para banco, Redis, OpenRouter, Resend ou AbacatePay:

- Upload DOCX valido com extracao e validacao de qualidade.
- Upload PDF valido com extracao via `pdfplumber` quando a dependencia esta instalada.
- Arquivo invalido, vazio, acima de 5 MB, content type incorreto, PDF corrompido e texto com marcadores crus de PDF.
- Quota anonima, bloqueio da quarta analise e rollback da reserva em falha.
- Magic link valido, expirado, reutilizado e payload que exige pagamento.
- Webhook AbacatePay assinado, assinatura invalida, pagamento duplicado, expirado, payload invalido e evento sem `billing_id`.
- OpenRouter com JSON invalido seguido de fallback e timeout esgotando o orcamento de tentativas.
- `/health` e `/api/v1/health` com resposta `ok`, `degraded` e `Cache-Control: no-store`.

Comando:

```bash
cd backend
pytest
```

## Cobertura Frontend

Os testes de frontend usam `node:test` para validar a superficie de deploy sem adicionar Playwright ou novas dependencias:

- Rewrite `/api/v1/:path*` aponta para `API_BASE_URL`.
- Headers mantem assets imutaveis cacheados e rotas privadas/API sem cache.
- Dropzone limita PDF/DOCX ate 5 MB antes do envio.
- Dashboard consulta quota antes da analise e direciona para login ou paywall.
- Modal PIX cria cobranca, escuta SSE de pagamento, trata confirmacao e expiracao.

Comandos:

```bash
cd frontend
npm run test:acceptance
npm run lint
npm run build
```

## Smoke Pos-Deploy

O script `scripts/vercel-smoke.mjs` valida previews ou staging antes de promocao:

- `GET /health` na API deve retornar HTTP 2xx e `status: "ok"`.
- `GET /` no frontend deve renderizar a shell do Parserly.
- Se `SMOKE_TEST_EMAIL` estiver definido, solicita magic link com e-mail de teste.
- Se `SMOKE_UPLOAD_FIXTURE` estiver definido, envia um PDF/DOCX pequeno para ambiente de staging preparado para nao gerar cobranca real.
- A resposta de `/health` e verificada contra nomes de variaveis sensiveis.

Comando:

```bash
API_PREVIEW_URL=https://parserly-api-preview.vercel.app \
FRONTEND_PREVIEW_URL=https://parserly-web-preview.vercel.app \
node scripts/vercel-smoke.mjs
```

Opcional:

```bash
SMOKE_TEST_EMAIL=teste@example.com \
SMOKE_UPLOAD_FIXTURE=fixtures/resume-smoke.pdf \
API_PREVIEW_URL=https://parserly-api-preview.vercel.app \
FRONTEND_PREVIEW_URL=https://parserly-web-preview.vercel.app \
node scripts/vercel-smoke.mjs
```

## Aceite Remoto

Ainda depende da conclusao remota da Fase 1:

- Projetos `parserly-web` e `parserly-api` criados na Vercel.
- Env vars completas em `preview` e `production`.
- Webhook publico configurado na AbacatePay.
- `VERCEL_TOKEN` valido nos secrets do GitHub.
- Preview real sem erro 5xx e logs revisados sem vazamento de dados sensiveis.

Quando esses bloqueios forem resolvidos, executar o workflow manual `Promote Vercel Preview` com as URLs reais de preview para fechar o aceite remoto antes da promocao.
