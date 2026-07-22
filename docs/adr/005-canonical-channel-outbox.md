# ADR 005 - Envelope canônico, inbox e outbox persistentes

Data: 2026-07-22

## Decisão

Todo gateway de canal deve entregar fatos de transporte ao serviço de aplicação
`services.conversations`; o gateway não grava conversas ou mensagens diretamente.
O serviço persiste evento externo, identidade externa, conversa, mensagem e
idempotência na mesma transação. Respostas externas são gravadas como mensagem e
evento de outbox na mesma transação.

## Consequências

- a chave de idempotência do evento externo é única globalmente e o identificador
  externo também é único por canal;
- o worker processa apenas outbox persistente, aplica backoff exponencial limitado
  e move falhas após cinco tentativas para `dead_letter`;
- sem um gateway ativo, nada é enviado externamente: o evento permanece auditável
  e é repetido de forma segura;
- o próximo gateway Telegram só poderá adaptar Update para esse serviço e
  entregar outbox, sem regras de domínio paralelas.
