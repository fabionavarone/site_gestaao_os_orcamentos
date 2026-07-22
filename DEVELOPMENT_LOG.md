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
