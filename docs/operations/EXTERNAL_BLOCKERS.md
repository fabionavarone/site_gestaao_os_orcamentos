# Bloqueios externos

Atualizado em 2026-07-22.

| Componente | Estado | Acao externa unica necessaria |
|---|---|---|
| Ativação Telegram externa | Cliente real, webhook, polling, mídia e outbox implementados e testados com Telegram fake; não há token autorizado | Cadastrar token pelo painel e validar `getMe`. |
| Webhook Telegram/HTTPS | Nginx e URL configurável implementados; sem domínio/certificado sob controle do projeto | Configurar `PUBLIC_BASE_URL`, DNS e TLS e acionar “Webhook”. |
| Ollama, Whisper, OCR e Piper | Modelos nao instalados no host | Disponibilizar os artefatos de modelo aprovados e capacidade de disco/RAM correspondente. |
| Publicação de porta no runtime gerenciado | Compose saudável e smoke interno aprovado, mas o runtime Docker não materializou a porta no host | Em host normal, publicar `PROVISAO_HTTP_PORT`; neste ambiente use smoke via `docker compose exec nginx`. |

Nenhum desses bloqueios impede o desenvolvimento do dominio, das interfaces,
das migracoes, dos testes unitarios ou dos contratos controlados.
