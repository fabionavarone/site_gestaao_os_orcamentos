# ADR 001 - MVP executavel sem dependencias externas

Data: 2026-07-22

## Contexto

O repositorio iniciou sem codigo, manifestos de dependencias ou Compose. O
blueprint exige operacao local, modo degradado sem IA e um servidor inicial com
recursos limitados.

## Decisao

O primeiro corte executavel usa Python 3.12 e biblioteca padrao: servidor HTTP,
SQLite, sessao por cookie e frontend estatico. O dominio fica concentrado em
`app/server.py` para provar o fluxo vertical antes de introduzir FastAPI,
PostgreSQL, Redis, containers e workers.

## Consequencias

- O MVP inicia sem download de pacotes e pode ser validado com `make test`.
- SQLite nao e a topologia de producao e deve migrar para PostgreSQL antes de
  concorrencia multiusuario real ou uso operacional externo.
- O endpoint Telegram e uma fronteira canonica de demonstracao; webhook real,
  segredo e envio externo permanecem pendentes.
