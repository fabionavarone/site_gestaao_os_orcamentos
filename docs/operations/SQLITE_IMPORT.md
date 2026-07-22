# Importacao do legado SQLite

1. Faça um backup verificavel do arquivo SQLite de origem.
2. Configure `DATABASE_URL` para o PostgreSQL de destino e aplique `alembic upgrade head`.
3. Execute `PYTHONPATH=apps/api python scripts/import_sqlite.py /caminho/legado.db --company "Nome da empresa"`.
4. Repita em ambiente de homologacao e compare as contagens de usuarios,
   clientes, equipamentos, OS, eventos, conversas, mensagens e auditoria.

O processo e idempotente por ID legado e usa uma transacao. Usuarios importados
ficam inativos pois o hash PBKDF legado nao e uma credencial Argon2 valida;
redefina a senha por fluxo administrativo antes de liberar acesso.
