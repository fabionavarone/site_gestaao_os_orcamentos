# Development Log

## Registro inicial

Projeto cadastrado pelo ai-switch em 2026-07-21 23:33:15.

Diretorio:

`/opt/provisao/site_gestaao_os_orcamentos`

## 2026-07-22 - Registro do blueprint mestre

- Lidos os documentos obrigatorios: `README.md`, `PROJECT_CONTEXT.md`,
  `DEVELOPMENT_LOG.md` e `HANDOFF_AI.md`.
- Recebido o Master Blueprint v3.0 do Provisao Manager.
- Criado `docs/product/MASTER_BLUEPRINT.md` com a especificacao mestre
  consolidada para orientar arquitetura, dominio, seguranca, IA local,
  Telegram, Web, roadmap e criterios de aceite.
- Atualizados `README.md` e `PROJECT_CONTEXT.md` para registrar produto,
  fase atual e proximo passo recomendado.
- Nenhum codigo de aplicacao foi criado nesta etapa.
- Testes executados: validacao documental por leitura/listagem de arquivos.

Proximo passo recomendado:

1. Validar pendencias de negocio da Fase 0.
2. Criar ADRs iniciais somente apos validacao minima: arquitetura monolito
   modular, stack backend/frontend, fila/jobs, armazenamento local e runtime de IA.
3. Depois disso, iniciar scaffold tecnico da Fase 1.

## 2026-07-22 - MVP operacional local

- Implementado `app/server.py`: servidor Web/API local com persistencia SQLite,
  sessao HTTP, RBAC inicial, auditoria e endpoints versionados.
- Implementada interface Web em `app/static/` para painel, clientes,
  equipamentos, OS, timeline de transicoes e caixa de entrada humana.
- Implementada maquina de estados de OS com bloqueio de transicoes invalidas e
  justificativa obrigatoria para estados sensiveis.
- Implementada fronteira de ingestao Telegram em formato canonico, com
  deduplicacao por identificador externo. Ela nao contem token nem acesso direto
  a banco fora da API.
- Criados testes em `tests/test_mvp.py`, `Makefile`, runbook local e ADR 001.
- Corrigida expiracao de sessao para usar timestamps ISO UTC consistentes.

Verificacoes executadas:

- `make test`: 3 testes aprovados.
- `python3 -m py_compile app/server.py scripts/run.py`: aprovado.
- `node --check app/static/app.js`: aprovado.
- Servidor iniciado na porta alternativa `8001` e `GET /api/v1/health` retornou
  `{"status": "ok", "database": "ok", "ai": "disabled"}`.
- Corrigido `scripts/run.py` para localizar a raiz do projeto quando executado
  diretamente.

Limitacao conhecida:

- O ambiente de testes bloqueia bind de socket local; os testes exercitam o
  handler HTTP em memoria. A execucao do servidor requer ambiente com permissao
  de rede local.

Proximo passo recomendado:

1. Homologar regras de negocio pendentes da Fase 0.
2. Substituir SQLite por PostgreSQL e introduzir migracoes.
3. Implementar worker/fila, arquivos e gateway Telegram real antes de expor o
   produto a usuarios externos.

## 2026-07-22 - Fundacao da refatoracao modular

- Confirmado diretorio e relida a documentacao obrigatoria integralmente.
- Preservado banco SQLite e arquivos do MVP em `backups/20260722T012150Z/`,
  com hashes SHA-256 em `SHA256SUMS`.
- Inicializado Git e criado baseline `bd5c533` antes de alterar a arquitetura.
- Criados Compose, configuracao de ambiente segura, Dockerfile Nginx/API e
  inicio da API modular FastAPI/SQLAlchemy.
- Novo nucleo introduz Argon2, sessoes com token persistido apenas por hash,
  expiracao/revogacao, CSRF para escritas, CORS configuravel, bloqueio
  progressivo de login e isolamento inicial por empresa.
- Dependencias foram instaladas somente em `.venv` local, ignorado pelo Git.
- A validacao de importacao/compilacao da API passou. Requests HTTP em memoria
  travaram no sandbox, portanto ainda nao ha declaracao de integracao HTTP
  aprovada; o bloqueio foi registrado em `docs/operations/EXTERNAL_BLOCKERS.md`.

## 2026-07-22 - Migracoes Alembic e importacao SQLite

- Criada a revisao Alembic `3e0c5f1889f9`, reversivel, para empresas, RBAC,
  CRM, equipamentos, OS, conversas e auditoria.
- O runtime nao cria mais tabelas; o schema e aplicado por Alembic.
- Implementado `scripts/import_sqlite.py`, transacional, idempotente e com
  preservacao de IDs e relacionamentos do banco legado.
- Hashes legados nao foram reutilizados como credenciais: usuarios importados
  ficam inativos ate uma redefinicao administrativa de senha.
- Validados upgrade, downgrade, novo upgrade e importacao repetida com fixture
  contendo todos os relacionamentos legados.

## 2026-07-22 - Organizacao e RBAC

- Adicionados unidades, equipes e membros de equipe na revisao Alembic
  `441a00f1e659`.
- Criadas rotas protegidas para cadastro de papeis, unidades, equipes e
  usuarios; permissoes e negacoes sao verificadas e auditadas no backend.
- Validado ciclo completo de upgrade/downgrade/upgrade das duas revisoes.

## 2026-07-22 - OS e caixa Web

- Criadas APIs tenant-scoped para criar OS, executar transicoes validas com
  optimistic locking e registrar historico imutavel de eventos.
- Criadas APIs para conversas e mensagens Web, separando nota interna de
  mensagem externa e auditando ambas.

## 2026-07-22 - Núcleo omnichannel persistente

- Criada a revisão Alembic `7a91bc4de220`, reversível, para canais, bots,
  identidades externas, participantes, eventos externos e outbox.
- Centralizada a ingestão canônica de canais em serviço de aplicação: ela cria
  identidade e conversa quando necessárias e deduplica por chave de idempotência
  e por evento externo do canal.
- Incluídos inbox com filtro, atribuição/pausa/encerramento humano e outbox
  transacional para respostas externas. O worker usa retry com backoff limitado
  e dead-letter após cinco falhas; nenhum transporte externo é chamado ainda.
- Testes aprovados: `test_omnichannel.py` (3 casos), compilação Python e ciclo
  Alembic upgrade/downgrade/upgrade em SQLite temporário.
- A suíte ASGI preexistente de segurança excedeu o limite de execução do sandbox
  durante Argon2; não foi alterada nem marcada como aprovada.

Próximo passo recomendado: implementar gateway Telegram real como adaptador do
serviço canônico, com token criptografado, webhook validado e contrato local fake.

Commit local criado: `8e2b0fb feat: add canonical omnichannel outbox`.
O push para `origin/main` falhou por resolução DNS de `github.com`; nenhuma
alteração local foi perdida.

## 2026-07-22 - Entrega vertical Telegram, uploads, Inbox React e outbox

- Criada a migração reversível `9c30f4a612ef` para completar canais, múltiplos
  bots, identidades, conversas, mensagens, eventos, locks e anexos privados.
- Tokens e segredo de webhook usam Fernet/MultiFernet; APIs retornam somente
  fingerprint mascarada e auditam administração sem credenciais.
- Implementados cliente Telegram real, webhook rápido e autenticado, polling de
  desenvolvimento, normalização de texto/imagem/voz/áudio/documento/vídeo,
  download limitado e storage local por assinatura e SHA-256.
- Inbox/outbox compartilham serviço canônico. Workers separados processam mídia,
  polling e entrega com lock expirável, jitter, `retry_after`, dead-letter e
  restauração transacional em falha.
- Criado frontend React/Vite/TypeScript/Tailwind/TanStack Query/React Hook Form:
  login, inbox, conversa, notas, upload, bots e entregas/dead-letter.
- Compose agora aplica migração antes da API/workers e inclui frontend, storage,
  healthchecks e Nginx. Builds Docker de API/frontend aprovados.
- Testes aprovados: backend modular (13), legado (3), frontend (3), compilação
  Python, TypeScript/Vite, Alembic upgrade/downgrade/upgrade e npm audit com zero
  vulnerabilidades. PostgreSQL confirmou revisão `9c30f4a612ef` e três tabelas
  centrais; smoke interno Nginx respondeu health e HTML React.
- Limitação externa: runtime Docker gerenciado não publicou porta no host; smoke
  equivalente foi executado dentro do Nginx. Não há token/domínio autorizado.
- Commits técnicos: `eb71aa6`, `280e928` e `7385902`; documentação registrada em
  commit separado na sequência.
- Commit documental `74f8c5c`. Push para `origin/main` tentado e não realizado
  por falha de resolução DNS de `github.com`; commits locais preservados.
- Auditoria final acrescentou reprocessamento administrativo de dead-letter da
  inbox e corrigiu “Assumir” para atribuir o usuário autenticado (`0e8723c`).

## 2026-07-22 - Fechamento operacional da Entrega Vertical 1

- A Inbox React passou a expor todos os filtros do backend, paginação e ações
  reais de assumir, transferir, devolver à fila, aguardar cliente/equipe,
  resolver, fechar/reabrir e pausar/retomar automação.
- Adicionado lookup tenant-scoped para seletores de atendente, equipe, cliente,
  equipamento e OS; vínculos deixam de exigir digitação manual de UUID.
- A tela de bots agora altera modo com o bot inativo, configura/remove webhook e
  consulta saúde e métricas. O token permanece somente mascarado.
- Testes finais aprovados: backend modular 13/13, legado 3/3, frontend 4/4,
  compileall, TypeScript/Vite e ciclo Alembic upgrade/downgrade/upgrade.
- Imagens Docker de API/frontend reconstruídas; PostgreSQL, Redis, API,
  inbox-worker, outbox-worker, frontend e Nginx ativos. Smoke interno retornou
  health da API, HTML React e revisão PostgreSQL `9c30f4a612ef`.
- `npm audit` havia registrado zero vulnerabilidades na validação anterior; a
  repetição final foi impedida exclusivamente pelo DNS do registry.
- Commit funcional: `8be9f5d feat: complete inbox operational controls`.

## 2026-07-22 - CRM de clientes, contatos e endereços

- Criada a revisão Alembic `d7a8e2c4b901`, reversível, com expansão de clientes
  PF/PJ, normalização de documentos/contatos, contatos, endereços e solicitações
  de merge.
- Implementadas rotas tenant-scoped para consulta, criação, atualização,
  detalhe, contatos, endereços e solicitação de merge; duplicidades não são
  mescladas automaticamente e retornam conflito auditável.
- Adicionada tela React Clientes com busca, cadastro e detalhe de contatos e
  endereços, conectada ao backend real.
- Testes finais do incremento: 19/19 backend modular, 3/3 legados, 5/5
  frontend, compileall, build Vite e ciclo Alembic upgrade/downgrade/upgrade.
- Commit: `3d06aad feat: deliver tenant scoped CRM operations`; push para
  `origin/main` concluído.

## 2026-07-22 - Catálogos e equipamentos

- Criada a revisão `e1b6c7d8f902` para categorias, marcas, modelos, campos
  completos de equipamento e acessórios, com ciclo reversível validado.
- Implementadas APIs tenant-scoped para catálogos, cadastro e busca de
  equipamentos, prevenção de duplicidade por serial/patrimônio e acessórios.
- Adicionada tela React Equipamentos com busca, cliente e cadastro real.
- Testes: 20/20 backend modular, 3/3 legados, 5/5 frontend, compileall e build
  Vite aprovados.

## 2026-07-22 - OS, recepção, triagem, tarefas e timeline

- Publicada a revisão `f2c3d4e5a601` com campos operacionais da OS, SLA,
  `service_order_tasks` e `service_order_triage`; ciclo Alembic reversível
  aprovado.
- Implementadas APIs para abertura pela conversa, numeração transacional,
  vínculo de workflow, detalhe, triagem, tarefas, estados e timeline interna ou
  pública. Eventos públicos usam o outbox Telegram existente.
- Frontend React ganhou lista/detalhe de OS, status, prioridade, SLA, triagem,
  tarefas e timeline.
- Testes: 21/21 backend modular, 3/3 legados, 5/5 frontend, compileall e
  build Vite aprovados.

## 2026-07-22 - Handoff da seção: OS em preparação

- A seção foi encerrada após os commits publicados `20e1b8f`, `4d9e760`,
  `3d06aad` e `411a2d9`.
- Estado publicado e validado: workflow persistente/versionado, CRM PF/PJ com
  contatos/endereço/duplicidade, catálogos de equipamento, equipamentos,
  acessórios, frontend Clientes/Equipamentos, Telegram da Entrega 1 intacto.
- Testes publicados: 20 backend modular, 3 legados, 5 frontend; builds Vite,
  compileall e ciclos Alembic CRM/equipamentos aprovados.
- Há trabalho local não commitado iniciado para OS: alteração em
  `apps/api/provisao_api/models.py` e migração
  `migrations/versions/f2c3d4e5a601_service_order_operations.py`, adicionando
  campos de operação/SLA, `service_order_tasks` e `service_order_triage`.
  Essa migração ainda precisa passar upgrade/downgrade/upgrade e revisão de
  constraints antes de commit.

## 2026-07-22 - Workflow persistente da Entrega Vertical 2

- Criada revisão `c4f23b1a9d02` com definições, versões, estados, transições,
  instâncias, eventos e execuções de ações, além de contador transacional de OS.
- Migração cria workflow publicado por empresa e vincula OS existentes sem
  alterar seus estados ou eventos. PostgreSQL local confirmou revisão, zero OS
  perdidas e zero OS sem instância.
- Motor valida grafo, condições declarativas e ações permitidas; publicação é
  imutável, clonagem preserva instâncias antigas e transições registram histórico.
- APIs e editor React cobrem definição, versão, estado, transição, validação,
  publicação, arquivamento, instâncias e histórico.
- Testes aprovados: backend 17/17, legado 3/3, frontend 5/5, compileall, build
  TypeScript/Vite e Alembic upgrade/downgrade/upgrade.
- Commits: `17865b8`, `8cd4676` e `a9d9488`.

## 2026-07-22 - Handoff técnico para próxima seção

- OS/recepção/triagem/tarefas/timeline foram publicados em `d160958` e
  documentados em `202095f`; a regressão modular permanece em 21 testes.
- Foi iniciado o próximo incremento com cinco modelos persistentes para
  diagnóstico versionado, medições, testes técnicos e checklists, além da
  migração `g3d4e5f6a702`.
- A migração candidata passou upgrade → downgrade → upgrade em SQLite
  temporário e `compileall` passou. Nenhum endpoint ou tela desses registros
  foi criado ainda; a entrega não está concluída.
- Próxima retomada: implementar `technical_api.py`, testes de ciclo de
  diagnóstico/checklist e formulários reais na tela de OS, depois concluir
  assistência técnica, notificações públicas, regressões e operação Docker.

## 2026-07-22 - Registros técnicos de OS

- Integrada a API `technical_api.py` e a migração candidata `g3d4e5f6a702` para
  diagnóstico versionado, medições, testes técnicos e checklists.
- Diagnósticos passam por draft, revisão e aprovação imutável; correções criam
  nova versão. Templates publicados são imutáveis e checklists obrigatórios
  validam conclusão. Auditoria e timeline são registradas.
- A tela React de OS possui ações reais para criar/revisar/aprovar diagnóstico,
  registrar medição/teste e aplicar checklist publicado.
- Evidências: backend 24/24, frontend 5/5, build Vite/TypeScript,
  compileall e ciclo Alembic upgrade → downgrade → upgrade aprovados.
- Próximo incremento: conclusão técnica, bancada/remoto/campo, agenda, entrega,
  garantia, retorno, notificações Telegram e E2E completo.

## 2026-07-22 - Atendimento e garantia de OS

- Criada a migração candidata `h4e5f6a7b803` para sessões de bancada/remoto/
  campo, visitas, entrega/retirada, garantias e retornos vinculados à OS.
- Criada `completion_api.py` com locks de sessão, estados de visita, fechamento
  por entrega, validação de período de garantia e abertura de OS de retorno.
- Testes de integração cobrem atendimento, visita, entrega, duplicidade,
  garantia e retorno. Evidências atuais: 26 testes backend, 5 frontend, build,
  compileall e Alembic upgrade/downgrade/upgrade aprovados.
- Próximo passo: tela React para essas operações, transições finais do workflow,
  notificações públicas Telegram e E2E completo.
