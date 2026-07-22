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
