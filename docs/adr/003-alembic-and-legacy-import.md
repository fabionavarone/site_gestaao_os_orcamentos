# ADR 003 - Alembic e importacao SQLite idempotente

Data: 2026-07-22

## Decisao

O schema da plataforma e criado exclusivamente por revisoes Alembic; o runtime
nao executa mais `create_all`. O importador em `scripts/import_sqlite.py` le o
banco legado em modo somente leitura, preserva os identificadores e executa a
escrita em uma unica transacao por execucao.

## Consequencias

- A execucao repetida e idempotente por identificador legado.
- Relacionamentos sao preservados pelas mesmas chaves UUID.
- O legado usa hash de senha incompativel com Argon2. Nenhuma senha e copiada
  como credencial valida: usuarios importados ficam inativos ate redefinicao
  administrativa, e o fato permanece auditavel.
