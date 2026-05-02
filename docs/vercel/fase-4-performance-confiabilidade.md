# Fase 4 - Performance e Confiabilidade

Status: concluida em 2026-05-02.

## Escopo Concluido

- Middleware de observabilidade adicionado com `trace_id`, metodo, path, status, duracao e `user_id` quando autenticado.
- Logs estruturados em JSON foram adicionados para requisicoes HTTP, OpenRouter, extracao de arquivos e eventos de pagamento.
- O endpoint `GET /health` foi criado para validar API, PostgreSQL e Redis.
- `backend/vercel.json` agora encaminha `/health` para a Function Python.
- Uploads passam por validacao antecipada de extensao, content type e tamanho declarado antes da leitura em chunks.
- O limite de arquivo continua em 5 MB, com exclusao do arquivo temporario no `finally`.
- O texto extraido e enviado ao OpenRouter apenas depois da validacao e e truncado para um limite operacional antes da chamada de IA.
- O orcamento total do OpenRouter foi limitado a 75s, abaixo do `maxDuration` de 120s da Function.
- O retry do OpenRouter foi limitado a duas tentativas: modelo principal e fallback.
- Dependencias pesadas de extracao e e-mail sao importadas sob demanda para reduzir trabalho no boot de rotas como `/health`, auth e pagamento.
- Redis recebeu timeouts curtos de conexao/socket e health check de conexao para reduzir travamentos em ambiente serverless.
- Solicitar magic link agora tem rate limit por e-mail e por IP via Redis.
- Webhooks de pagamento expirado foram ajustados para resposta idempotente por `billing_id`.

## Metas de Producao

- LCP da pagina inicial abaixo de 2,5s.
- Upload aceito ou rejeitado em menos de 1s antes da chamada IA.
- P95 da analise abaixo de 30s quando OpenRouter responder dentro do esperado.
- Webhook de pagamento processado em menos de 3s.

## Alertas Minimos na Vercel

Configurar no projeto `parserly-api` quando ele existir na Vercel:

- Erros 5xx acima do baseline normal.
- Timeouts ou `FUNCTION_INVOCATION_FAILED`.
- Logs com `event=openrouter_request_failed` ou `event=openrouter_retry_budget_timeout`.
- Logs com `event=abacatepay_create_charge_failed`.
- Falhas no endpoint `GET /health`.

Configurar no projeto `parserly-web`:

- Erros 5xx.
- LCP acima de 2,5s nas paginas publicas.

## Validacao

Antes de promover producao, validar:

```powershell
python -m compileall backend/app
python -c "from app.main import app; print(app.title)"
```

Com a API em preview:

- `GET /health` retorna `status=ok` quando banco e Redis estao acessiveis.
- Upload invalido ou maior que 5 MB retorna erro antes da chamada OpenRouter.
- Logs de upload e IA mostram metadados operacionais, nunca conteudo de curriculo.
- Webhook duplicado por `billing_id` retorna status idempotente.
