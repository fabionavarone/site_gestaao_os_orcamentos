# ADR 006 - Credenciais Telegram, storage privado e workers

Data: 2026-07-22

## Decisão

- Tokens e segredos de webhook são cifrados com Fernet/MultiFernet, uma cifra
  autenticada. A chave atual e chaves antigas de rotação vêm exclusivamente do
  ambiente; o banco guarda somente ciphertext, hash/fingerprint e metadados.
- Webhook e polling persistem o mesmo `ExternalEvent`. A resposta HTTP do
  webhook termina após validação, deduplicação e commit; mídia é baixada pelo
  worker de inbox.
- Arquivos usam storage local privado, chave aleatória, escrita atômica, SHA-256,
  detecção por assinatura e endpoint autenticado. Nginx não publica o volume.
- Inbox, outbox e polling são processos do monólito modular, não serviços com
  domínio próprio. A outbox usa lock persistente expirável, backoff com jitter,
  `retry_after` do Telegram e dead-letter.

## Consequências

Telegram real funciona quando credencial e URL HTTPS forem configuradas. Sem
elas, o mesmo cliente é validado por contrato com transporte Telegram fake. A
entrega é no mínimo uma vez: lock e idempotência impedem concorrência local,
mas uma interrupção depois de o Telegram aceitar e antes do commit pode exigir
conferência pelo `telegram_message_id` registrado.
