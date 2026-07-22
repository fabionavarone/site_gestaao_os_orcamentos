# ADR 002 - Fundacao modular segura

Data: 2026-07-22

## Decisao

O MVP legado permanece preservado em `backups/20260722T012150Z/` e no commit
baseline. A nova aplicacao passa a ser construida em `apps/api`, com FastAPI,
SQLAlchemy 2, Alembic, PostgreSQL e Redis. O Compose publica somente Nginx em
`127.0.0.1:8080`; banco, Redis e API ficam em rede interna.

## Seguranca inicial

- credenciais nao sao versionadas; `.env.example` contem somente valores
  seguros de exemplo;
- senha usa Argon2; sessoes armazenam somente hash do bearer, expiram e podem
  ser revogadas;
- escritas exigem token CSRF e cookie HttpOnly/SameSite;
- login aplica bloqueio progressivo;
- CORS usa allowlist configuravel;
- empresa e parte obrigatoria dos registros novos.

## Consequencias

O schema final sera aplicado apenas por Alembic, nunca por `create_all` em
producao. A migracao SQLite para PostgreSQL sera idempotente e validada antes
da troca de runtime. Telegram, IA e TLS publico ficam desligados ate haver
segredos, dominio/certificado e capacidade operacional reais.
