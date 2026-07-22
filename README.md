# site_gestaao_os_orcamentos

Projeto cadastrado pelo ai-switch.

## Diretorio

`/opt/provisao/site_gestaao_os_orcamentos`

## Produto

Este repositorio sera usado para construir o Provisao Manager: uma plataforma
inteligente de atendimento multimodal e gestao completa de assistencia tecnica
para a Provisao Sistemas.

O blueprint mestre esta em:

- `docs/product/MASTER_BLUEPRINT.md`

Estado atual: migracoes e importacao legada concluidas. O MVP legado foi preservado e a
nova fundacao modular FastAPI/PostgreSQL/Redis/Compose esta em `apps/api/` e
`infra/`; ela ainda nao substituiu o runtime legado.

## Fase atual

Entrega vertical Telegram, uploads, Inbox React e outbox concluída no código.

Consulte `docs/operations/LOCAL_RUNBOOK.md` para iniciar e testar o sistema.

Implementado neste corte:

- autenticacao local baseada em sessao e papeis;
- clientes e equipamentos vinculados;
- criacao de OS, timeline auditavel e maquina de estados;
- caixa de entrada Web, mensagens externas e notas internas;
- fronteira canonica e idempotente para updates Telegram;
- testes automatizados sem dependencias externas.
- API modular para OS com transicoes persistidas, bloqueio otimista e timeline;
- API de conversas Web com mensagens internas e externas auditadas.
- múltiplos bots Telegram com token cifrado, webhook, polling de desenvolvimento,
  texto e mídia por cliente Bot API real;
- storage privado com MIME real, hash, escrita atômica e download autorizado;
- Inbox React responsiva para conversa, filtros/paginação, atribuição,
  transferência, esperas, vínculos com cliente/equipamento/OS, pausa da
  automação, notas, anexos, bots, saúde/métricas e dead-letter;
- workers de inbox/outbox com locks, retry, backoff, rate limit e auditoria;
- Compose com migração, PostgreSQL, Redis, API, workers, frontend e Nginx.
- workflow persistente e versionado, publicação imutável, editor React,
  instâncias/histórico e migração das OS existentes;
- CRM tenant-scoped com clientes PF/PJ, normalização, duplicidade auditável,
  contatos, endereços e interface de clientes;
- catálogos tenant-scoped de categorias, marcas e modelos, equipamentos
  completos, acessórios e interface React de equipamentos;
- operações de OS com abertura pela conversa, numeração, vínculo ao workflow,
  SLA inicial, recepção/triagem, tarefas, timeline interna/pública e tela React;

Ativação externa depende apenas de token autorizado e domínio/TLS. Consulte
`docs/operations/TELEGRAM_AND_INBOX.md`.

Operação do motor de fluxo: `docs/operations/WORKFLOW.md`.
Operação do CRM: APIs em `/api/v1/crm` e tela Clientes no painel Web.

Handoff da seção atual: `HANDOFF_AI.md` registra o estado exato da Entrega
Vertical 2 e a retomada do incremento de OS.

O incremento técnico local adiciona diagnóstico versionado, medições, testes
técnicos e checklists com API tenant-scoped e ações reais na tela de OS; a
conclusão técnica, entrega e garantia permanecem como próxima unidade.

Também está implementada localmente a API de sessões de bancada/remoto/campo,
visitas, entrega/retirada, garantia e retorno, na migração candidata
`h4e5f6a7b803`; o frontend específico dessas ações ainda deve ser ampliado.
Eventos públicos dessas operações reutilizam o outbox Telegram existente.
O painel React agora possui a tela Atendimento para iniciar sessões, concluir
tecnicamente, agendar visita e registrar retirada usando essas APIs reais.

Para encerrar esta seção e retomá-la em outra sessão, leia primeiro
`README.md`, `PROJECT_CONTEXT.md`, `DEVELOPMENT_LOG.md` e `HANDOFF_AI.md`.
O último commit publicado é `202095f`; há uma migração/modelos locais ainda
não publicados para diagnósticos, medições, testes técnicos e checklists. O
handoff contém o comando exato, evidências e a ordem segura de continuação.

## Regras

- Trabalhar somente dentro deste diretorio.
- Nao alterar outros projetos em `/opt/provisao` sem autorizacao explicita.
- Nao copiar arquivos de outros projetos sem autorizacao explicita.
- Ler `docs/product/MASTER_BLUEPRINT.md` antes de alterar arquitetura ou dominio.
