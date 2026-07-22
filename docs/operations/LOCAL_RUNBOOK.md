# Execucao local

## Iniciar

```bash
make run
```

Abra `http://127.0.0.1:8000`.

Credenciais iniciais, somente para ambiente local:

- e-mail: `admin@provisao.local`
- senha: `provisao123`

O banco SQLite e criado em `data/provisao_manager.db`. Esse diretorio nao deve
ser versionado. Antes de qualquer exposicao de rede, altere a senha inicial e
substitua a autenticacao local pelo provedor aprovado.

## Verificar

```bash
make test
curl http://127.0.0.1:8000/api/v1/health
```

## Limites atuais

Este corte implementa Web, autenticacao local, clientes, equipamentos, OS,
timeline auditavel e atendimento humano. Nao habilita Telegram real, upload de
arquivos, PDF, IA, estoque, financeiro, portal do cliente ou PostgreSQL.
