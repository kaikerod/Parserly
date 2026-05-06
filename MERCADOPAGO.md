# Mercado Pago

> Guia local de integracao para o gateway de pagamentos do Parserly. A implementacao usa Checkout Transparente via API Payments para gerar PIX dentro do modal.

## Fluxo PIX

- Criar pagamento com `POST https://api.mercadopago.com/v1/payments`.
- Enviar `Authorization: Bearer <MERCADOPAGO_ACCESS_TOKEN>`.
- Enviar `X-Idempotency-Key` com um UUID unico por cobranca.
- Corpo principal:
  - `transaction_amount`: valor em reais, por exemplo `19.90`.
  - `description`: descricao curta do pacote.
  - `payment_method_id`: `pix`.
  - `payer.email`: e-mail do usuario autenticado.
  - `external_reference`: referencia unica da cobranca no Parserly.
  - `date_of_expiration`: data/hora de expiracao do QR Code no formato ISO 8601 com milissegundos e offset, por exemplo `2026-05-03T15:30:00.000+00:00`.
  - `notification_url`: URL publica HTTPS de `/api/v1/payments/webhook`.
  - `metadata.user_id`: UUID do usuario para auditoria.
- A resposta retorna o ID do pagamento em `id`.
- O QR Code vem em `point_of_interaction.transaction_data.qr_code_base64`.
- O Pix copia e cola vem em `point_of_interaction.transaction_data.qr_code`.
- O link hospedado, se for necessario, vem em `point_of_interaction.transaction_data.ticket_url`.

## Webhooks

- Mercado Pago envia notificacoes para `POST /api/v1/payments/webhook`.
- A autenticidade e validada com:
  - Header `x-signature`, no formato `ts=<timestamp>,v1=<hmac>`.
  - Header `x-request-id`.
  - Query param `data.id`.
  - Segredo `MERCADOPAGO_WEBHOOK_SECRET`.
- O manifesto usado no HMAC e:

```text
id:{data.id};request-id:{x-request-id};ts:{ts};
```

- A notificacao traz o ID do pagamento, mas a liberacao de credito deve consultar `GET https://api.mercadopago.com/v1/payments/{id}` antes de alterar quota.
- Status processados:
  - `approved`: marcar pagamento como `paid` e liberar creditos.
  - `cancelled`, `canceled`, `rejected`, `expired`, `refunded`, `charged_back`: marcar pagamento pendente como `expired`.
  - Demais status permanecem sem efeito colateral.

## Variaveis

```bash
API_PUBLIC_URL=https://api.parserly.com.br
MERCADOPAGO_ACCESS_TOKEN=...
MERCADOPAGO_API_URL=https://api.mercadopago.com
MERCADOPAGO_WEBHOOK_SECRET=...
ANALYSIS_PRICE_CENTS=1990
```

Em desenvolvimento local, `API_PUBLIC_URL=http://localhost:...` nao deve ser enviado ao Mercado Pago porque `notification_url` precisa ser uma URL publica HTTPS. O backend omite esse campo para gerar o QR Code localmente; para receber confirmacao automatica por webhook no dev, exponha a API com um tunel HTTPS e use essa URL em `API_PUBLIC_URL`.

## Referencias Oficiais

- Pix via API Payments: https://www.mercadopago.com.br/developers/en/docs/checkout-api-payments/integration-configuration/integrate-pix
- Criar pagamento: https://www.mercadopago.com.br/developers/es/reference/online-payments/checkout-api-payments/create-payment/post
- Obter pagamento: https://www.mercadopago.com.br/developers/en/reference/online-payments/checkout-pro/get-payment/get
- Validacao de webhooks: https://www.mercadopago.com.br/developers/en/docs/checkout-pro/payment-notifications
