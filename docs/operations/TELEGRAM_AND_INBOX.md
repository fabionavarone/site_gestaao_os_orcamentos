# Telegram, uploads e Inbox

## Configuração segura

Gere a chave de cifra fora do repositório:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Defina `TELEGRAM_TOKEN_ENCRYPTION_KEY` no `.env` protegido. Para rotação, coloque
a chave nova como atual e as antigas, separadas por vírgula, em
`TELEGRAM_TOKEN_ENCRYPTION_PREVIOUS_KEYS`; substitua/rotacione os tokens antes de
remover uma chave antiga. Nunca copie as chaves, tokens ou segredo de webhook
para logs ou documentação.

Também configure `PUBLIC_BASE_URL` com a origem HTTPS pública. O painel permite:

1. cadastrar e validar o token via `getMe`;
2. selecionar `webhook`, `polling` ou `disabled`;
3. ativar/desativar, substituir token e configurar/remover webhook;
4. consultar saúde, último erro, entregas e dead-letter.

O token nunca volta ao navegador; apenas a fingerprint mascarada é exibida.
Polling só é executado por `polling-worker` em `development` ou `staging`, usando
o profile `polling`, e nunca para um bot configurado como webhook.

## Storage e limites

O volume `uploads_data` é privado e montado em `STORAGE_ROOT`. Nomes originais
são somente metadados; a chave física é aleatória. Assinatura real, tamanho,
SHA-256 e allowlist são verificados para imagem, áudio/voz, documento e MP4.
Temporários são escritos atomicamente e removidos. Downloads passam por sessão,
tenant e auditoria em `/api/v1/attachments/{id}/download`.

Limites são controlados por `MAX_IMAGE_BYTES`, `MAX_AUDIO_BYTES`,
`MAX_DOCUMENT_BYTES`, `MAX_VIDEO_BYTES` e `MAX_UPLOAD_BYTES`.

## Processos

```bash
docker compose up -d postgres redis migrate api inbox-worker outbox-worker frontend nginx
docker compose --profile polling up -d polling-worker
```

- `inbox-worker`: normaliza update, cria/reutiliza identidade e conversa, baixa
  mídia e grava anexos na mesma unidade transacional;
- `outbox-worker`: reivindica lock, envia texto/arquivo, registra `sent`, retry ou
  dead-letter;
- `polling-worker`: busca updates, persiste offset e usa a mesma deduplicação;
- `migrate`: aplica Alembic antes de API e workers.

Use `PROVISAO_HTTP_PORT` para trocar a porta local publicada, se necessário.

## Testes e diagnóstico

```bash
PYTHONPATH=apps/api python -m unittest discover -s apps/api/tests -v
cd frontend-web && npm test && npm run build
ENV_FILE=.env.example POSTGRES_PASSWORD=change-me docker compose config --quiet
```

Os testes `test_telegram_vertical.py` e `test_telegram_api.py` implementam o
servidor Telegram fake para `getMe`, `getFile`, download, webhook e envio.
Consulte logs estruturados sem conteúdo sensível:

```bash
docker compose logs -f api inbox-worker outbox-worker polling-worker
```

Itens definitivos aparecem na tela Entregas e podem ser reprocessados por usuário
com `telegram.manage`. Rate limit respeita `retry_after`; locks interrompidos são
recuperados após `OUTBOX_LOCK_SECONDS`.

Na Inbox, filtros de canal, bot, estado, equipe, responsável e prioridade usam
as rotas reais. A conversa permite assumir/transferir, retornar à fila, marcar
esperas, resolver/fechar, pausar automação e vincular cliente, equipamento e OS.
Os seletores são carregados por `/api/v1/conversation-options` e retornam somente
registros da empresa autenticada.

## Backup e restauração do storage

Pare os workers ou garanta snapshot consistente, copie o volume `uploads_data`
com ferramenta aprovada e grave SHA-256 do arquivo de backup. Para restaurar,
reponha o volume antes de iniciar os workers e valide amostras comparando o hash
da tabela `attachments`. O banco e o volume devem pertencer ao mesmo ponto de
restauração.
