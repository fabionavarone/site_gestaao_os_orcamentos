# Bloqueios externos

Atualizado em 2026-07-22.

| Componente | Estado | Acao externa unica necessaria |
|---|---|---|
| Telegram real | Sem token de bot autorizado | Fornecer token por canal seguro, nunca neste repositorio. |
| Webhook Telegram/HTTPS | Sem dominio e certificado sob controle do projeto | Disponibilizar DNS e certificado/proxy TLS. |
| Ollama, Whisper, OCR e Piper | Modelos nao instalados no host | Disponibilizar os artefatos de modelo aprovados e capacidade de disco/RAM correspondente. |
| Validacao HTTP real no ambiente atual | Sandbox bloqueia bind local e requests ASGI ficam sem conclusao | Executar a suite Compose em host com rede local habilitada. |

Nenhum desses bloqueios impede o desenvolvimento do dominio, das interfaces,
das migracoes, dos testes unitarios ou dos contratos controlados.
