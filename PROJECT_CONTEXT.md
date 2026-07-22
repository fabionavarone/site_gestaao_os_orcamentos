# Project Context

Projeto: site_gestaao_os_orcamentos

Diretorio: /opt/provisao/site_gestaao_os_orcamentos

Este projeto deve permanecer isolado dos demais projetos dentro de /opt/provisao.

## Produto

O projeto agora tem como especificacao mestre o Provisao Manager, uma plataforma
de atendimento inteligente multimodal e omnichannel para assistencia tecnica.

Documento base:

- `docs/product/MASTER_BLUEPRINT.md`

## Arquitetura-alvo resumida

- Monolito modular com processos separados quando houver necessidade operacional.
- Backend FastAPI, frontend React/Vite/TypeScript, PostgreSQL, Redis e workers.
- Telegram e Web compartilham o mesmo nucleo de identidade, conversa, estado,
  fluxo, regras e dados.
- IA local atua apenas na interpretacao, classificacao, extracao e assistencia;
  regras de negocio, permissoes, persistencia e auditoria ficam no backend.
- Fluxos devem ser versionados, persistentes e testaveis, nunca apenas prompts.

## Estado atual

- Fase atual: migracoes, importacao e escopos organizacionais concluídos.
- Legado preservado: `app/server.py`, frontend estatico e SQLite continuam
  disponiveis somente como referencia/backup.
- Nova aplicacao: `apps/api/`, com Compose em `docker-compose.yml`.
- Persistencia alvo: PostgreSQL, com revisao Alembic e importador SQLite
  idempotente em `scripts/import_sqlite.py`.
- Documentacao de produto: `docs/product/MASTER_BLUEPRINT.md`.
- Execucao e limites: `docs/operations/LOCAL_RUNBOOK.md`.
- Decisao de arquitetura do corte: `docs/adr/001-stdlib-mvp.md`.
- OS possuem transicoes persistidas e versionadas na API modular; conversas Web
  e mensagens compartilham a mesma auditoria.
- O núcleo de canais normaliza a persistência de eventos externos e mensagens:
  `channels`, identidades externas, eventos deduplicados e outbox existem na
  revisão `7a91bc4de220`. O worker aplica retry com backoff e dead-letter.
- A revisão `9c30f4a612ef` completa bots, identidades, estados de conversa e
  mensagem, locks, anexos e métricas. Telegram real usa webhook ou polling sobre
  os mesmos eventos. O frontend operacional está em `frontend-web/`.
- A Inbox oferece a cadeia humana completa: filtros e paginação, assumir,
  transferir por atendente/equipe, devolver à fila, esperas, resolver/fechar,
  pausar automação e vincular cliente, equipamento e OS usando seletores
  isolados pela empresa. A administração de bots expõe modo, webhook, saúde e
  métricas sem retornar credenciais.
- A revisão `c4f23b1a9d02` introduz workflow persistente/versionado, publicação
  imutável, instâncias e histórico. O workflow padrão preserva os estados
  existentes e novas OS usam numeração transacional por empresa.
- A revisão `d7a8e2c4b901` amplia o CRM com pessoa física/jurídica, campos
  normalizados, contatos, endereços e solicitações de merge. As rotas
  `/api/v1/crm` e a tela Clientes são tenant-scoped e auditadas.
- A revisão `e1b6c7d8f902` adiciona categorias, marcas, modelos, campos
  completos do equipamento e acessórios; APIs `/api/v1/equipment` e tela
  Equipamentos usam as mesmas regras de empresa e auditoria.
- O próximo incremento de OS foi iniciado localmente, mas ainda não está
  estabilizado nem publicado: `models.py` contém campos de contato/endereço,
  conversa, origem, tipo de atendimento, equipe/técnico, SLA e timestamps; a
  migração candidata é `f2c3d4e5a601_service_order_operations.py`.
- A revisão `f2c3d4e5a601` foi estabilizada e publicada: OS podem ser abertas
  pela conversa, recebem número transacional, workflow e SLA, e possuem
  triagem, tarefas, timeline pública/interna e detalhe React.

## Proximo passo recomendado

Próximo incremento da Entrega Vertical 2: diagnóstico versionado, medições,
testes técnicos, checklists e conclusão técnica. A migração `f2c3d4e5a601` está
publicada.
Em paralelo, validar pendencias de negocio:

- categorias de equipamento do MVP;
- documentos atuais a reproduzir;
- matriz de permissoes e alcadas;
- estados e SLA;
- politica de desconto, garantia, abandono e retencao;
- metodo de vinculo com Telegram;
- horario de automacao e atendimento humano;
- filas iniciais;
- catalogo inicial de intencoes com exemplos reais;
- quais fluxos podem criar OS e quais criam apenas rascunho.

## Registros técnicos locais - 2026-07-22

Foi integrado `technical_api.py` e criada a migração candidata
`g3d4e5f6a702` para diagnósticos versionados, medições, testes técnicos e
checklists. O backend e a interface React de OS já expõem criação, revisão,
aprovação, aplicação e validação de checklist. A unidade foi validada com 24
testes backend, 5 frontend, build TypeScript/Vite, compileall e ciclo Alembic.
Conclusão técnica, atendimento especializado, entrega, garantia e retorno ainda
devem ser implementados.

O backend local já recebeu `completion_api.py` e a revisão candidata
`h4e5f6a7b803` para sessões de trabalho, visitas, entrega/retirada, garantia e
retorno. A API e os testes passam; a interface React correspondente e a
integração com transições/notificações ainda são o próximo incremento.

Eventos públicos de entrega, garantia e retorno passaram a enfileirar mensagens
via o outbox Telegram existente quando aplicável; conteúdo interno permanece
fora do canal externo.

A conclusão técnica da OS está protegida por diagnóstico aprovado e pela
conclusão de tarefas/checklists obrigatórios.

## Estado para retomada em nova seção - 2026-07-22

O último commit publicado é `202095f`. A próxima unidade começou localmente
com os modelos de diagnóstico, medições, testes técnicos e checklists em
`apps/api/provisao_api/models.py` e a migração candidata
`migrations/versions/g3d4e5f6a702_technical_records_and_checklists.py`.
`compileall` e o ciclo Alembic upgrade/downgrade/upgrade em SQLite temporário
passaram. Ainda faltam serviço, API, autorização, auditoria, testes e React;
retomar por esses itens sem recriar os módulos publicados.
