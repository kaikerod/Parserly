# PRD — ATS Resume Analyzer
**Versão:** 1.0 (MVP)
**Status:** Em Revisão
**Autor:** Product & Engineering
**Última atualização:** 2026-05-01

---

## Índice

1. [Visão Geral do Produto](#1-visão-geral-do-produto)
2. [Tech Stack e Arquitetura de Alto Nível](#2-tech-stack-e-arquitetura-de-alto-nível)
3. [Fluxo de Usuário](#3-fluxo-de-usuário)
4. [Histórias de Usuário](#4-histórias-de-usuário)
5. [Requisitos Funcionais e Integrações](#5-requisitos-funcionais-e-integrações)
6. [Requisitos Não Funcionais](#6-requisitos-não-funcionais)
7. [Tratamento de Exceções e Edge Cases](#7-tratamento-de-exceções-e-edge-cases)

---

# 1. Visão Geral do Produto

## 1.1 Problema

A maioria dos currículos submetidos a processos seletivos é eliminada automaticamente por sistemas ATS (Applicant Tracking System) antes de ser lida por um recrutador humano. Os candidatos desconhecem os critérios técnicos que determinam essa filtragem — densidade de palavras-chave, formatação compatível com parsers, estrutura de seções e hierarquia de informação — e não dispõem de ferramentas acessíveis para diagnosticar e corrigir essas deficiências antes do envio.

## 1.2 Solução

Uma aplicação web que:

1. Recebe o arquivo de currículo do usuário (PDF ou DOCX).
2. Extrai o conteúdo textual do arquivo no backend.
3. Envia o conteúdo ao modelo de IA via OpenRouter com um prompt estruturado de avaliação ATS.
4. Retorna ao usuário um relatório com nota de otimização ATS (0–100), diagnóstico por categoria e recomendações acionáveis.

## 1.3 Escopo do MVP

**Incluído:**
- Upload de arquivo PDF/DOCX.
- Até 3 análises gratuitas para visitantes sem cadastro.
- Identificação/cadastro por e-mail obrigatório após o visitante consumir os 3 usos grátis (sem senha, via Magic Link — ver seção 3.1).
- Contagem de análises por visitante anônimo e por usuário cadastrado.
- Integração com OpenRouter para processamento via IA.
- Paywall ativo após esgotamento da quota gratuita, com checkout via AbacatePay.
- Relatório de análise estruturado exibido na interface.

**Excluído do MVP:**
- Comparação de currículos entre si.
- Edição de currículo dentro da plataforma.
- Integração com LinkedIn ou portais de emprego.
- Painel administrativo.
- Planos de assinatura recorrente (o MVP suporta apenas pagamento por análise avulsa).

---

# 2. Tech Stack e Arquitetura de Alto Nível

## 2.1 Tech Stack

| Camada | Tecnologia | Justificativa |
|---|---|---|
| **Backend** | Python 3.12 + FastAPI | Async nativo, tipagem estática, suporte a Pydantic v2 |
| **Extração de texto** | `pdfplumber` (PDF), `python-docx` (DOCX) | Bibliotecas maduras, sem dependência de serviços externos |
| **Banco de dados** | PostgreSQL 16 | ACID, suporte a JSON para armazenar o relatório bruto |
| **ORM** | SQLAlchemy 2.x (async) + Alembic | Migrações versionadas |
| **Cache / Filas** | Redis | Cache de sessão e fila de jobs assíncronos |
| **Frontend** | Next.js 14 (App Router) + Tailwind CSS | SSR, rotas de API, DX consistente |
| **Autenticação** | Magic Link via e-mail (Resend API) | Sem fricção de senha; identifica usuário sem cadastro completo |
| **IA** | OpenRouter API | Abstração de múltiplos LLMs; fallback de modelo configurável |
| **Pagamentos** | AbacatePay API | Gateway nacional, PIX nativo |
| **Infraestrutura** | Docker + Railway (ou Fly.io) | Deploy simplificado para MVP |
| **Armazenamento de arquivos** | Armazenamento temporário em disco (S3-compatible no pós-MVP) | Arquivos descartados após extração de texto |

## 2.2 Arquitetura de Alto Nível

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENTE (Browser)                     │
│          Next.js 14 — UI de upload, relatório, paywall       │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTPS / REST
┌─────────────────────▼───────────────────────────────────────┐
│                    BACKEND (FastAPI)                          │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │   Router    │  │   Service    │  │    Repository      │  │
│  │  (HTTP In)  │→ │  (Lógica)   │→ │  (DB / Cache)      │  │
│  └─────────────┘  └──────┬───────┘  └────────────────────┘  │
│                           │                                  │
│              ┌────────────┼──────────────┐                   │
│              ▼            ▼              ▼                   │
│        [Extrator]   [OpenRouter]   [AbacatePay]              │
│        PDF/DOCX      API Client     API Client               │
└─────────────────────────────────────────────────────────────┘
                      │                   │
              ┌───────▼───────┐   ┌───────▼───────┐
              │  PostgreSQL   │   │     Redis      │
              │  (principal)  │   │  (sessão/fila) │
              └───────────────┘   └───────────────┘
```

## 2.3 Estrutura de Diretórios do Backend

```
app/
├── api/
│   └── v1/
│       ├── routers/
│       │   ├── auth.py
│       │   ├── analysis.py
│       │   └── payments.py
│       └── __init__.py
├── services/
│   ├── auth_service.py
│   ├── analysis_service.py
│   ├── file_service.py
│   ├── openrouter_service.py
│   └── payment_service.py
├── repositories/
│   ├── user_repository.py
│   └── analysis_repository.py
├── models/
│   ├── user.py
│   ├── analysis.py
│   └── payment.py
├── schemas/
│   ├── analysis.py
│   └── payment.py
├── core/
│   ├── config.py
│   ├── security.py
│   └── exceptions.py
└── main.py
```

---

# 3. Fluxo de Usuário

## 3.1 Autenticação, Cadastro e Identificação

O sistema permite o primeiro uso como visitante e utiliza **Magic Link** para cadastro/identificação do usuário sem exigir senha. O cadastro passa a ser obrigatório após o visitante consumir os 3 usos grátis.

**Fluxo:**

```
1. Visitante acessa a página inicial e pode iniciar a análise sem cadastro
2. Backend identifica o visitante por cookie HTTPOnly e contabiliza usos no Redis
3. Após 3 análises gratuitas, nova tentativa retorna `registration_required`
4. Frontend direciona o visitante ao cadastro por e-mail
5. Backend gera token único (UUID v4, TTL: 15 minutos) e armazena no Redis
6. Backend envia e-mail com link de acesso (ex: /auth/verify?token=<UUID>)
7. Usuário clica no link
8. Backend valida token → cria sessão JWT (HTTPOnly cookie, TTL: 7 dias)
9. Usuário é redirecionado ao dashboard de upload
10. Caso o e-mail não exista no banco, cria registro de usuário automaticamente
```

**Nota de implementação:** O token Magic Link deve ser invalidado no Redis imediatamente após primeiro uso (one-time use).

## 3.2 Upload e Análise (Quota Gratuita)

```
1. Visitante ou usuário autenticado faz upload do arquivo na dropzone
2. Frontend valida: tipo de arquivo (PDF/DOCX), tamanho máximo (5 MB)
3. Frontend envia arquivo via POST /api/v1/analysis (multipart/form-data)
4. Backend executa verificação de quota:
   ├── SE visitante_anônimo e usos_grátis < 3: prossegue para extração
   ├── SE visitante_anônimo e usos_grátis >= 3: retorna HTTP 401 `registration_required` → Frontend direciona ao cadastro
   ├── SE usuário autenticado e análises_usadas < 3: prossegue para extração
   └── SE usuário autenticado e análises_usadas >= 3: retorna HTTP 402 → Frontend exibe paywall
5. Backend extrai texto do arquivo (pdfplumber ou python-docx)
6. Backend envia texto ao OpenRouter (modelo configurado) com prompt ATS
7. Backend aguarda resposta da IA (timeout: 60s)
8. Backend parseia resposta e persiste análise no PostgreSQL
9. Backend retorna relatório estruturado ao frontend
10. Frontend renderiza relatório (nota, diagnóstico por categoria, recomendações)
```

## 3.3 Paywall e Checkout (AbacatePay)

```
1. Frontend recebe HTTP 402 do backend
2. Frontend exibe modal de paywall com:
   ├── Mensagem: "Você atingiu o limite de 3 análises gratuitas"
   ├── Valor da análise avulsa
   └── Botão "Pagar e Analisar"
3. Usuário clica em "Pagar e Analisar"
4. Frontend chama POST /api/v1/payments/create-charge
5. Backend cria cobrança na AbacatePay API e retorna:
   ├── URL de checkout (redirecionamento) ou
   └── QR Code PIX + código Copia e Cola
6. Frontend exibe QR Code PIX ao usuário
7. AbacatePay envia webhook para POST /api/v1/payments/webhook ao confirmar pagamento
8. Backend valida assinatura do webhook (HMAC-SHA256)
9. Backend registra crédito de +1 análise ao usuário no banco
10. Backend emite evento via Redis Pub/Sub → Frontend recebe via SSE (Server-Sent Events)
11. Frontend fecha modal e libera a análise automaticamente
12. Backend processa análise (retorna ao passo 5 do fluxo 3.2)
```

## 3.4 Diagrama de Estados do Usuário

```
[Anônimo - Free]
(usos_grátis: 0–2)
        │
(faz análise)
        │
        ▼
[Cadastro Obrigatório]
(usos_grátis: 3)
        │
(insere e-mail)
        │
        ▼
[Aguardando Magic Link]
        │
(clica no link)
        │
        ▼
[Autenticado - Free]
(análises_usadas: 0–2)
        │
(faz análise)
        │
        ▼
[Free - Quota Esgotada]
(análises_usadas: 3)
        │
(paga via AbacatePay)
        │
(webhook confirmado)
        │
        ▼
[Crédito Adicionado]
(pode fazer 1 nova análise)
```

---

# 4. Histórias de Usuário

As histórias estão ordenadas por prioridade para o MVP.

## US-01 — Identificação por E-mail

**Como** visitante que consumiu os 3 usos grátis,
**quero** inserir meu e-mail para receber um link de acesso,
**para que** eu possa me cadastrar e continuar usando a plataforma sem criar senha.

**Critérios de Aceite:**
- O sistema aceita apenas endereços de e-mail com formato válido (RFC 5322).
- O link de acesso expira em 15 minutos.
- O link é invalidado após o primeiro uso.
- Se o e-mail ainda não existe no banco, um registro de usuário é criado automaticamente.
- O cadastro só é exigido para visitantes após a terceira análise gratuita.

---

## US-02 — Upload e Análise de Currículo (Quota Gratuita)

**Como** visitante com menos de 3 usos grátis ou usuário autenticado com quota disponível,
**quero** fazer upload do meu currículo em PDF ou DOCX,
**para que** eu receba uma nota de otimização ATS e recomendações.

**Critérios de Aceite:**
- Formatos aceitos: `.pdf`, `.docx`.
- Tamanho máximo: 5 MB.
- O sistema rejeita arquivos de outros tipos com mensagem de erro específica.
- O relatório é exibido na mesma página, sem redirecionamento.
- O contador de análises é incrementado somente após o relatório ser gerado com sucesso.
- Ao atingir 3 usos grátis sem cadastro, o visitante é direcionado ao cadastro por e-mail.

---

## US-03 — Visualização do Relatório de Análise

**Como** usuário que submeteu um currículo,
**quero** ver o relatório com nota, categorias analisadas e recomendações,
**para que** eu saiba exatamente o que preciso melhorar.

**Critérios de Aceite:**
- O relatório exibe: nota geral (0–100), nota por categoria (ex: palavras-chave, formatação, estrutura, contato), e lista de recomendações priorizadas.
- Cada recomendação indica o impacto esperado na nota.
- O relatório é persistido no banco e pode ser consultado novamente via `/analysis/{id}`.

---

## US-04 — Paywall ao Atingir Quota Gratuita

**Como** usuário que esgotou as 3 análises gratuitas,
**quero** ser informado claramente sobre o limite e ter a opção de continuar pagando,
**para que** eu possa decidir se quero pagar sem confusão.

**Critérios de Aceite:**
- O modal de paywall exibe o preço por análise avulsa e o método de pagamento (PIX).
- O usuário não é redirecionado para outra página; o checkout ocorre dentro de um modal.
- O sistema não inicia nenhuma análise antes da confirmação do pagamento.
- Para visitantes anônimos, o bloqueio após 3 usos grátis é de cadastro, não de pagamento.

---

## US-05 — Pagamento via PIX (AbacatePay)

**Como** usuário no paywall,
**quero** pagar por uma análise adicional via PIX,
**para que** eu possa continuar usando a plataforma imediatamente após o pagamento.

**Critérios de Aceite:**
- O QR Code PIX e o código Copia e Cola são exibidos dentro do modal.
- Após confirmação de pagamento (via webhook), o modal fecha automaticamente e a análise é iniciada sem nova interação do usuário.
- O prazo máximo de expiração do QR Code é de 30 minutos.
- Em caso de expiração sem pagamento, o usuário pode solicitar a geração de um novo QR Code.

---

## US-06 — Histórico de Análises

**Como** usuário recorrente,
**quero** visualizar o histórico das minhas análises anteriores,
**para que** eu possa acompanhar minha evolução.

**Critérios de Aceite:**
- O histórico lista análises com: data, nome do arquivo e nota obtida.
- O usuário pode clicar em uma análise para ver o relatório completo.
- Análises de sessões anteriores são exibidas, desde que o mesmo e-mail seja usado.

---

# 5. Requisitos Funcionais e Integrações

## 5.1 Módulo de Autenticação

| ID | Requisito |
|---|---|
| AUTH-01 | O endpoint `POST /api/v1/auth/request-link` gera e envia Magic Link ao e-mail informado |
| AUTH-02 | O endpoint `GET /api/v1/auth/verify` valida o token e emite cookie JWT HTTPOnly |
| AUTH-03 | O JWT tem TTL de 7 dias e é renovado automaticamente a cada requisição autenticada |
| AUTH-04 | O endpoint `POST /api/v1/auth/logout` invalida o cookie e registra o token JWT em blocklist no Redis |
| AUTH-05 | Rate limit de Magic Link: máximo 3 solicitações por e-mail a cada 10 minutos |

## 5.2 Módulo de Análise

| ID | Requisito |
|---|---|
| ANA-01 | O endpoint `POST /api/v1/analysis` aceita `multipart/form-data` com campo `file` |
| ANA-02 | O backend verifica a quota do visitante anônimo ou `analyses_used` do usuário antes de iniciar qualquer processamento |
| ANA-03 | A extração de texto falha com erro `422` se o arquivo estiver corrompido, protegido por senha ou vazio |
| ANA-04 | O resultado da análise é persistido com os campos: `id`, `user_id`, `score`, `report_json`, `filename`, `created_at` |
| ANA-05 | O endpoint `GET /api/v1/analysis/{id}` retorna a análise por ID, validando que pertence ao usuário da sessão |
| ANA-06 | O endpoint `GET /api/v1/analysis` retorna lista paginada das análises do usuário (padrão: 10 por página) |

## 5.3 Integração com OpenRouter

### 5.3.1 Configuração da Requisição

```python
# Exemplo de estrutura da chamada
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": settings.APP_URL,
    "X-Title": "ATS Resume Analyzer"
}

payload = {
    "model": settings.OPENROUTER_MODEL,  # ex: "google/gemma-4-26b-a4b-it:free"
    "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": resume_text}
    ],
    "temperature": 0.2,
    "max_tokens": 2048,
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "ats_resume_analysis",
            "strict": True,
            "schema": ANALYSIS_RESPONSE_SCHEMA
        }
    }
}
```

### 5.3.2 System Prompt (Canônico)

```
Você é um especialista em sistemas ATS (Applicant Tracking Systems) e otimização de currículos.

Analise o currículo fornecido e retorne **exclusivamente** um objeto JSON válido com a seguinte estrutura:

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
- Não inclua markdown, texto livre ou explicações fora do JSON.
- O campo "overall_score" deve ser a média ponderada das categorias (keywords: 35%, formatting: 20%, structure: 20%, contact_info: 10%, quantifiable_achievements: 15%).
- Ordene "recommendations" da maior para menor prioridade.
- Limite "recommendations" a 7 itens.
- Se o texto não for um currículo reconhecível, retorne overall_score: 0 e recommendations com uma única entrada explicando o problema.
```

### 5.3.3 Tratamento de Timeout e Retry

```python
# Configuração do cliente HTTP assíncrono
OPENROUTER_TIMEOUT = httpx.Timeout(
    connect=5.0,    # 5s para estabelecer conexão
    read=60.0,      # 60s para leitura da resposta
    write=10.0,
    pool=5.0
)

RETRY_CONFIG = {
    "max_attempts": 3,
    "wait_exponential_multiplier": 1,  # 1s, 2s, 4s
    "retry_on": [429, 500, 502, 503, 504]
}
```

- Timeout total máximo: 90 segundos (incluindo retries).
- Se o modelo principal falhar após 3 tentativas, o sistema usa o modelo de fallback definido em `settings.OPENROUTER_FALLBACK_MODEL`.
- Se ambos falharem, retorna HTTP 503 ao cliente com mensagem de erro padronizada.

### 5.3.4 Validação da Resposta da IA

```python
def validate_ai_response(raw: dict) -> AnalysisReport:
    """
    - Verifica se todos os campos obrigatórios estão presentes
    - Valida que scores estão no range [0, 100]
    - Valida que priority é um dos valores permitidos
    - Em caso de falha de validação, registra log e lança ParseError
    """
```

- O schema de validação é implementado com Pydantic v2.
- Respostas com JSON malformado disparam `json.JSONDecodeError`, logado e propagado como `AIResponseError`.

## 5.4 Integração com AbacatePay

### 5.4.1 Criação de Cobrança

**Endpoint backend:** `POST /api/v1/payments/create-charge`

**Fluxo:**
1. Backend chama `POST https://api.abacatepay.com/v1/billing/create` com:
   - `amount`: valor em centavos (ex: `1990` para R$ 19,90).
   - `methods`: `["PIX"]`.
   - `products`: `[{"name": "Análise ATS Avulsa", "quantity": 1, "price": 1990}]`.
   - `customer.email`: e-mail do usuário autenticado.
   - `metadata.user_id`: UUID do usuário (para reconciliação no webhook).
   - `expiresIn`: `1800` (30 minutos em segundos).
2. Persiste o `billing_id` retornado no banco, associado ao `user_id` e com `status: "pending"`.
3. Retorna ao frontend: `{ "pix_qr_code": "...", "pix_copy_paste": "...", "expires_at": "..." }`.

### 5.4.2 Recebimento e Validação do Webhook

**Endpoint backend:** `POST /api/v1/payments/webhook`

```python
def validate_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Valida o header X-Abacatepay-Signature usando HMAC-SHA256
    com a chave ABACATEPAY_WEBHOOK_SECRET definida em variáveis de ambiente.
    Retorna False se a assinatura não coincidir — nunca lança exceção.
    """
    expected = hmac.new(
        settings.ABACATEPAY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**Lógica de processamento:**

```
1. Receber payload bruto (bytes) antes de deserializar
2. Validar assinatura HMAC → se inválida: retornar HTTP 401 e logar
3. Deserializar payload JSON
4. Verificar event type:
   ├── "billing.paid": incrementar análises disponíveis (+1) no user_id extraído de metadata
   ├── "billing.expired": atualizar status do billing para "expired" no banco
   └── outros eventos: logar e retornar HTTP 200 (idempotência)
5. Atualizar status do billing no banco
6. Publicar evento "analysis_unlocked:{user_id}" no Redis Pub/Sub
7. Retornar HTTP 200 imediatamente (AbacatePay exige resposta em < 5s)
```

**Idempotência:** Antes de incrementar a quota, verificar se `billing_id` já foi processado. Se sim, retornar HTTP 200 sem efeitos colaterais.

### 5.4.3 Notificação em Tempo Real ao Frontend

O frontend mantém uma conexão SSE (Server-Sent Events) com `GET /api/v1/payments/status-stream` após exibir o QR Code. O backend publica o evento via Redis Pub/Sub quando o webhook é confirmado, e o SSE entrega ao cliente:

```json
{ "event": "payment_confirmed", "analysis_credits": 1 }
```

---

# 6. Requisitos Não Funcionais

## 6.1 Performance

| Métrica | Target | Observação |
|---|---|---|
| Tempo de resposta da análise (P95) | ≤ 30s | Inclui extração + chamada IA |
| Tempo de resposta da análise (P99) | ≤ 60s | Limite hard do timeout da IA |
| Confirmação de pagamento (webhook → SSE) | ≤ 3s | Após confirmação da AbacatePay |
| Throughput mínimo simultâneo | 20 análises concorrentes | Garantido pela natureza async do FastAPI |
| Disponibilidade do serviço | 99% uptime | Excluindo janelas de manutenção planejadas |

## 6.2 Segurança

### 6.2.1 Arquivos de Currículo

- Arquivos são armazenados em diretório temporário com permissões `0700`.
- O texto é extraído imediatamente após o upload; o arquivo binário é deletado do disco após extração, independente de sucesso ou falha (`try/finally`).
- O nome original do arquivo é sanitizado com `secure_filename()` antes de qualquer operação de I/O.
- Arquivos com tamanho zero ou superior a 5 MB são rejeitados antes de serem escritos no disco.

### 6.2.2 Autenticação e Sessão

- Cookies JWT com atributos: `HttpOnly`, `Secure`, `SameSite=Strict`.
- JWT não contém dados sensíveis — apenas `user_id` (UUID) e `exp`.
- Blocklist de tokens no Redis para suporte a logout explícito.

### 6.2.3 API Keys e Segredos

- Todas as chaves de API (`OPENROUTER_API_KEY`, `ABACATEPAY_API_KEY`, `ABACATEPAY_WEBHOOK_SECRET`) são carregadas exclusivamente via variáveis de ambiente.
- Nenhuma chave deve aparecer em logs, rastreamentos de erro ou respostas de API.

### 6.2.4 Validação de Input

- Tamanho máximo de payload: 6 MB (5 MB de arquivo + overhead multipart).
- Content-Type validado no backend, independente do que o frontend enviar.
- Sanitização de todos os campos de texto antes de persistência.

### 6.2.5 Rate Limiting

| Endpoint | Limite |
|---|---|
| `POST /auth/request-link` | 3 req / 10 min por IP e por e-mail |
| `POST /analysis` | 10 req / hora por `user_id` |
| `POST /payments/create-charge` | 5 req / hora por `user_id` |
| `POST /payments/webhook` | Sem rate limit (IP da AbacatePay whitelistado) |

## 6.3 Privacidade de Dados

- O conteúdo do currículo enviado ao OpenRouter não é associado a dados identificáveis do usuário no prompt (o texto do currículo é enviado de forma isolada, sem e-mail ou nome de usuário).
- O `report_json` armazenado no banco não replica o conteúdo bruto do currículo — armazena apenas o resultado estruturado da análise.
- Política de retenção: análises são retidas por 90 dias após criação; após esse prazo, o `report_json` é anonimizado (user_id setado para null e dados de contato removidos do JSON).

## 6.4 Observabilidade

- Structured logging em JSON em todas as requisições (biblioteca: `structlog`).
- Campos obrigatórios em todo log: `trace_id`, `user_id` (quando disponível), `endpoint`, `duration_ms`, `status_code`.
- Nunca logar: conteúdo do currículo, API keys, dados de pagamento, tokens JWT.
- Health check endpoint: `GET /health` retornando status do banco e Redis.

---

# 7. Tratamento de Exceções e Edge Cases

## EC-01 — Timeout da API do OpenRouter

**Cenário:** A requisição ao OpenRouter não retorna resposta dentro do timeout configurado (60s de leitura).

**Causa provável:** Sobrecarga do modelo, rede instável ou prompt excessivamente longo.

**Comportamento esperado:**

```
1. O cliente HTTP (httpx) lança TimeoutException
2. O serviço executa retry com backoff exponencial (tentativas: 3)
3. Na segunda tentativa, o sistema usa o modelo de fallback (settings.OPENROUTER_FALLBACK_MODEL)
4. Se todas as tentativas falharem:
   a. Registrar erro no log com trace_id, modelo, tentativas e duração total
   b. NÃO incrementar analyses_used do usuário
   c. Retornar HTTP 503 ao cliente:
      { "error": "analysis_unavailable", "message": "Serviço de análise temporariamente indisponível. Tente novamente em alguns minutos." }
5. Frontend exibe mensagem de erro com botão "Tentar novamente"
```

---

## EC-02 — Arquivo Corrompido, Protegido por Senha ou com Texto Não Extraível

**Cenário:** O usuário envia um PDF que está criptografado com senha, corrompido, ou é um PDF de imagem (scan) sem camada de texto pesquisável.

**Comportamento esperado:**

```
1. O extrator de texto retorna string vazia ou lança exceção específica
2. O serviço de análise detecta o caso (len(text) < MIN_RESUME_CHARS = 100):
   a. NÃO chamar o OpenRouter
   b. NÃO incrementar analyses_used
   c. Deletar arquivo temporário
   d. Retornar HTTP 422:
      {
        "error": "unprocessable_file",
        "reason": "<password_protected|corrupted|image_only|insufficient_content>",
        "message": "Não foi possível extrair texto do arquivo. Verifique se o PDF não está protegido por senha e contém texto selecionável."
      }
3. Frontend exibe a mensagem de erro com sugestões específicas baseadas no campo "reason"
```

---

## EC-03 — Webhook do AbacatePay Recebido em Duplicidade

**Cenário:** O AbacatePay reenvia o mesmo evento de pagamento confirmado (comportamento esperado em sistemas de pagamento por garantia de entrega).

**Comportamento esperado:**

```
1. Backend recebe webhook com billing_id já registrado no banco
2. Antes de processar: consulta tabela payments WHERE billing_id = X AND status = 'paid'
3. Se registro encontrado:
   a. NÃO incrementar analyses_used novamente
   b. Retornar HTTP 200 imediatamente (sinaliza ao AbacatePay que o evento foi recebido)
   c. Logar warning: "Duplicate webhook received for billing_id: X"
4. Se registro NÃO encontrado: processar normalmente (ver seção 5.4.2)
```

---

## EC-04 — Usuário Tenta Burlar o Paywall por Múltiplas Contas com o Mesmo Dispositivo

**Cenário:** Usuário cria contas com e-mails diferentes para acumular análises gratuitas.

**Mitigação implementada no MVP:**

```
1. Ao gerar Magic Link, associar um "device fingerprint" (hash de User-Agent + Accept-Language + IP) ao usuário
2. Armazenar fingerprint na tabela users (campo: device_fingerprints JSONB, aceita múltiplos)
3. Se fingerprint já existir em outro user_id com analyses_used >= 3:
   a. Não bloquear imediatamente (falsos positivos possíveis)
   b. Sinalizar flag: users.suspicious = true
   c. Reduzir quota gratuita do novo registro para 1 análise
   d. Registrar log de auditoria
```

**Nota:** Bloqueio hard com base em fingerprint não é implementado no MVP para evitar falsos positivos (ex: usuários em redes corporativas com IP compartilhado). A flag `suspicious` serve de insumo para revisão manual no pós-MVP.

---

## EC-05 — Expiração do QR Code PIX Antes do Pagamento

**Cenário:** O usuário visualiza o QR Code mas não realiza o pagamento dentro de 30 minutos.

**Comportamento esperado:**

```
1. Frontend mantém contador regressivo visível ao usuário
2. Ao atingir 0: SSE recebe evento "payment_expired" OU frontend detecta expiração localmente
3. Frontend desabilita código Copia e Cola e exibe botão "Gerar novo código"
4. Usuário clica em "Gerar novo código":
   a. Frontend chama POST /api/v1/payments/create-charge novamente
   b. Billing anterior permanece com status "expired" no banco (não é reutilizado)
   c. Novo QR Code é exibido
5. Rate limit de /payments/create-charge (5 req/hora) previne abuso desse fluxo
```

---

## EC-06 — Resposta da IA com JSON Malformado ou Schema Inválido

**Cenário:** O modelo retorna texto que não é JSON válido, ou JSON com campos ausentes/fora do range esperado.

**Comportamento esperado:**

```
1. Validação Pydantic falha ao tentar parsear a resposta
2. Sistema registra resposta bruta completa no log (nível ERROR) com trace_id
3. Sistema executa uma segunda tentativa com prompt mais restritivo adicionando:
   "ATENÇÃO: Sua resposta anterior não era JSON válido. Retorne APENAS o objeto JSON, sem texto adicional."
4. Se a segunda tentativa também falhar:
   a. NÃO incrementar analyses_used
   b. Retornar HTTP 503 com erro genérico ao usuário
   c. Registrar incidente para revisão do prompt
```

---

## Apêndice A — Modelo de Dados (Tabelas Principais)

```sql
-- Usuários
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    analyses_used   INTEGER NOT NULL DEFAULT 0,
    suspicious      BOOLEAN NOT NULL DEFAULT false,
    device_fingerprints JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Análises
CREATE TABLE analyses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    filename        VARCHAR(255) NOT NULL,
    score           SMALLINT CHECK (score BETWEEN 0 AND 100),
    report_json     JSONB NOT NULL,
    model_used      VARCHAR(100) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Pagamentos
CREATE TABLE payments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    billing_id      VARCHAR(255) UNIQUE NOT NULL,  -- ID retornado pela AbacatePay
    amount_cents    INTEGER NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending | paid | expired | refunded
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at    TIMESTAMPTZ
);

-- Índices
CREATE INDEX idx_analyses_user_id ON analyses(user_id);
CREATE INDEX idx_payments_billing_id ON payments(billing_id);
CREATE INDEX idx_payments_user_status ON payments(user_id, status);
```

---

## Apêndice B — Variáveis de Ambiente Obrigatórias

```bash
# Aplicação
APP_URL=https://atsanalyzer.com.br
SECRET_KEY=<string aleatória 64 chars>
ENVIRONMENT=production

# Banco de Dados
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/ats_db

# Redis
REDIS_URL=redis://host:6379/0

# E-mail (Magic Link)
RESEND_API_KEY=re_...
EMAIL_FROM=noreply@atsanalyzer.com.br

# OpenRouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=google/gemma-4-26b-a4b-it:free
OPENROUTER_FALLBACK_MODEL=google/gemma-4-26b-a4b-it:free

# AbacatePay
ABACATEPAY_API_KEY=...
ABACATEPAY_WEBHOOK_SECRET=...
ANALYSIS_PRICE_CENTS=1990
```

---

*Fim do documento. Versão 1.0 — MVP.*
