# Execução local modular

## Iniciar

Copie `.env.example` para um `.env` não versionado, gere segredos próprios e
defina uma senha forte de bootstrap. O projeto não fornece credenciais padrão.

```bash
docker compose up -d
```

Abra `http://127.0.0.1:8080` ou a porta definida em `PROVISAO_HTTP_PORT`.

## Verificar

```bash
PYTHONPATH=apps/api python -m unittest discover -s apps/api/tests -v
cd frontend-web && npm test && npm run build
curl http://127.0.0.1:8080/api/v1/health
```

## Limites atuais

Token Telegram e domínio/TLS são configurações externas. Sem eles, use polling
de desenvolvimento ou os testes Telegram fake documentados em
`TELEGRAM_AND_INBOX.md`. IA, PDF, estoque, financeiro e portal permanecem fora
desta entrega vertical.
