# Handoff entre IAs

Data e hora da geracao: 2026-07-22 01:45:00 UTC

Nome do projeto selecionado: site_gestaao_os_orcamentos

Diretorio do projeto: /opt/provisao/site_gestaao_os_orcamentos

Objetivo do handoff: permitir que a proxima IA continue o projeto com seguranca, usando a documentacao local como fonte principal antes de qualquer alteracao.

## Arquivos obrigatorios para leitura antes de qualquer alteracao

- README.md
- DEVELOPMENT_LOG.md
- HANDOFF_AI.md
- PROJECT_CONTEXT.md, se existir

## Regra universal para a proxima IA

Sempre verificar os arquivos .md obrigatorios antes de alterar qualquer arquivo do projeto. Usar esses arquivos como fonte principal para entender objetivo, estado atual, fases concluidas, fase em andamento, arquivos importantes, testes ja executados, pendencias e proximo passo recomendado.

## Estado Docker

`docker-compose.yml` foi introduzido para PostgreSQL, Redis, API, worker e
Nginx. Ainda requer `.env` local seguro e validacao em host com Docker/rede.

## Status local

{"status":"ok","database":"ok"}

## Atualizacao em 2026-07-22

O Master Blueprint v3.0 do Provisao Manager foi recebido e consolidado em:

- `docs/product/MASTER_BLUEPRINT.md`

O projeto passa a ter como objetivo construir o Provisao Manager: plataforma
multimodal e omnichannel de atendimento e gestao de assistencia tecnica para a
Provisao Sistemas.

Estado atual:

- Fase atual: fundacao da migracao modular.
- Legado preservado em `backups/20260722T012150Z/` e commit `bd5c533`.
- Novo nucleo em `apps/api/`; PostgreSQL/Redis ainda nao foram inicializados.
- Testes: `make test` aprovado em 2026-07-22 (3 testes).
- Validacao manual: servidor local respondeu em `/api/v1/health` na porta 8001.
- Documentacao de produto: registrada em `docs/product/MASTER_BLUEPRINT.md`.

Prioridade para a proxima IA:

1. Ler `docs/product/MASTER_BLUEPRINT.md` antes de alterar arquitetura, dominio
   ou codigo.
2. Ler `docs/adr/001-stdlib-mvp.md` e `docs/operations/LOCAL_RUNBOOK.md` antes
   de substituir o corte local por infraestrutura de producao.
3. Aplicar `alembic upgrade head` e homologar o importador SQLite antes de uso
   multiusuario real.
4. Manter Telegram como gateway sem acesso direto ao banco.
5. Manter IA local desacoplada das transacoes e com saidas validadas por schema.
6. Nunca tratar o endpoint demonstrativo Telegram como webhook de producao sem
   autenticacao do gateway, criptografia de segredos e rate limiting.

## Atualizacao 2026-07-22

As revisões Alembic, importação SQLite, organização/RBAC, API de OS, caixa Web
e núcleo omnichannel estão em commits posteriores ao baseline. A revisão
`7a91bc4de220` introduz canais, identidades externas, eventos idempotentes e
outbox com retry/dead-letter. O serviço em
`apps/api/provisao_api/services/conversations.py` é a única fronteira de
persistência que Telegram e Web devem compartilhar.

Próximo incremento: gateway Telegram configurável e real, adaptado a esse
serviço. Não criar acesso do bot ao banco nem enviar diretamente da request.

Último commit local: `8e2b0fb feat: add canonical omnichannel outbox`.
O push para `origin/main` foi tentado e permaneceu pendente por falha de DNS
para `github.com`; o commit local está preservado e a árvore estava limpa.

## Entrega vertical 1 - estado de 2026-07-22

A cadeia Telegram → evento → conversa/anexo → Inbox React → resposta → outbox →
Telegram foi implementada. Migração atual: `9c30f4a612ef`. Serviços principais:
`services/telegram.py`, `inbox_worker.py`, `delivery.py`, `storage.py` e
`crypto.py`. Interface: `frontend-web/`. Operação:
`docs/operations/TELEGRAM_AND_INBOX.md`.

Evidências antes do commit: 13 testes backend, 3 legados e 3 frontend aprovados;
build Vite e imagens Docker aprovados; npm audit zerado; ciclo Alembic reversível
aprovado; Compose/PostgreSQL/Redis/API/workers/frontend/Nginx saudáveis; smoke
interno respondeu `/api/v1/health` e o HTML React. A porta externa não foi
publicada pelo runtime gerenciado, embora a configuração Docker tenha o binding.

Próximo comando exato após checkout/configuração de ambiente:

```bash
ENV_FILE=.env POSTGRES_PASSWORD='<valor-do-ambiente>' docker compose up -d
```

Para homologação externa, cadastrar token pela tela Bots, configurar
`PUBLIC_BASE_URL` HTTPS e ativar webhook. Nenhum segredo foi versionado.

Commits da entrega:

- `eb71aa6 feat: deliver secure Telegram messaging vertical`;
- `280e928 feat: add React inbox and Telegram operations UI`;
- `7385902 ops: run vertical stack with healthchecks`.

Serviços foram deixados ativos e saudáveis no Compose local, exceto o profile
opcional de polling. A árvore deve ficar limpa após o commit documental final.

Commit documental: `74f8c5c docs: document Telegram vertical operations`.
O push final foi tentado e falhou apenas por resolução DNS de `github.com`; os
commits à frente de `origin/main` permanecem preservados localmente.

Após a auditoria, `0e8723c` adicionou a tela/API de dead-letter da inbox e
corrigiu atribuição ao assumir conversa. Backend (13) e frontend (3) passaram
novamente; o branch permanece à frente de `origin/main`.

Fechamento adicional em `8be9f5d`: a Inbox agora possui filtros completos,
paginação, transferências, fila/esperas, pausa da automação e vínculos por
seletores tenant-scoped. A tela Bots cobre mudança de modo, configuração e
remoção de webhook, saúde e métricas. Evidências finais: backend modular 13/13,
legado 3/3, frontend 4/4, Vite/TypeScript, compileall e Alembic reversível. O
stack reconstruído está ativo; smoke interno confirmou API, frontend e revisão
PostgreSQL `9c30f4a612ef`. A única ativação não executada é externa e exige token
Telegram e domínio/TLS autorizados. O push segue dependente de DNS para GitHub.

## Entrega Vertical 2 em andamento

Workflow concluído nos commits `17865b8`, `8cd4676` e `a9d9488`. Revisão atual:
`c4f23b1a9d02`. O PostgreSQL local foi migrado e confirmou zero OS sem instância.
Regressão: 17 testes backend, 3 legados e 5 frontend aprovados; build Vite e
ciclo Alembic reversível aprovados. Próximo requisito incompleto: CRM completo,
contatos, endereços e duplicidades. Comando de retomada:

```bash
git status --short --branch && PYTHONPATH=apps/api .venv/bin/python -m unittest discover -s apps/api/tests -v
```

## Ultimos logs da API

Logs da API nao encontrados ou servico api nao existe.

## Git status

Git nao configurado neste diretorio.

## Regras obrigatorias para a proxima IA

- Nao refazer fases concluidas.
- Nao apagar arquivos sem necessidade.
- Nao alterar credenciais.
- Nao expor tokens.
- Nao iniciar nova fase sem entender o estado documentado.
- Nao declarar o sistema finalizado sem evidencias.
- Nao alterar arquitetura ou dominio sem ler `docs/product/MASTER_BLUEPRINT.md`.
- Ao final de qualquer alteracao, atualizar README.md, DEVELOPMENT_LOG.md, HANDOFF_AI.md e PROJECT_CONTEXT.md.

## Prompt obrigatorio para a proxima IA

Leia README.md, HANDOFF_AI.md, PROJECT_CONTEXT.md e DEVELOPMENT_LOG.md, se existirem, antes de alterar qualquer arquivo.

Projeto selecionado:
site_gestaao_os_orcamentos

Diretorio do projeto:
/opt/provisao/site_gestaao_os_orcamentos

Depois execute:

pwd
Continue exatamente do ponto documentado.
Trabalhe por fases.
Teste antes de declarar qualquer fase concluida.
Atualize README.md, DEVELOPMENT_LOG.md, HANDOFF_AI.md e PROJECT_CONTEXT.md ao final.

## Atualização CRM - 2026-07-22

O incremento `3d06aad` entregou CRM tenant-scoped: clientes PF/PJ, campos
normalizados, conflito de duplicidade, contatos, endereços, solicitações de
merge, API `/api/v1/crm` e tela React Clientes. A migração `d7a8e2c4b901` passou
upgrade/downgrade/upgrade em SQLite temporário. A suíte modular passou 19 testes,
a legada 3 e a frontend 5. O commit está publicado em `origin/main`.

Próximo comando: implementar catálogos e equipamentos completos, preservando o
workflow `c4f23b1a9d02` e o CRM `d7a8e2c4b901`.

## Atualização de equipamentos - 2026-07-22

A revisão `e1b6c7d8f902` e o incremento atual entregam categorias, marcas,
modelos, equipamentos completos, acessórios, prevenção de duplicidade e tela
React Equipamentos. A suíte modular está em 20 testes aprovados; a próxima
unidade é OS pela conversa, recepção, triagem e timeline técnica.

## Handoff de encerramento da seção - 2026-07-22

### Estado Git

Branch `main` está sincronizada com `origin/main` no commit publicado
`20e1b8f feat: deliver equipment catalogs and accessories`. Há alterações locais
intencionais ainda não commitadas:

- `apps/api/provisao_api/models.py` — campos operacionais adicionais em
  `ServiceOrder`, mais `ServiceOrderTask` e `ServiceOrderTriage`;
- `migrations/versions/f2c3d4e5a601_service_order_operations.py` — migração
  candidata para esses campos/tabelas.

Não declarar essa unidade concluída antes de corrigir/testar a migração.

### Evidências publicadas

- Workflow: commits `17865b8`, `8cd4676`, `a9d9488`, `8fc01e4`.
- CRM: commits `411a2d9`, `3d06aad`, `4d9e760`; revisão `d7a8e2c4b901`.
- Equipamentos: commit `20e1b8f`; revisão `e1b6c7d8f902`.
- Testes: `PYTHONPATH=apps/api .venv/bin/python -m unittest discover -s apps/api/tests -v` → 20 aprovados; `make test` → 3 aprovados; `frontend-web/npm test` → 5 aprovados; `npm run build` aprovado; `compileall` aprovado.
- Alembic CRM/equipamentos: upgrade → downgrade → upgrade aprovado em SQLite temporário.

### Retomada exata

```bash
cd /opt/provisao/site_gestaao_os_orcamentos
pwd
git status --short --branch
git diff --check
PYTHONPATH=apps/api .venv/bin/python -m compileall -q apps/api/provisao_api
tmp_db=$(mktemp /tmp/provisao-os-XXXXXX.db)
APP_SECRET_KEY=test-secret-with-sufficient-length DATABASE_URL=sqlite+pysqlite:///$tmp_db REDIS_URL=redis://localhost:6379/0 PYTHONPATH=apps/api .venv/bin/alembic upgrade head
APP_SECRET_KEY=test-secret-with-sufficient-length DATABASE_URL=sqlite+pysqlite:///$tmp_db REDIS_URL=redis://localhost:6379/0 PYTHONPATH=apps/api .venv/bin/alembic downgrade e1b6c7d8f902
APP_SECRET_KEY=test-secret-with-sufficient-length DATABASE_URL=sqlite+pysqlite:///$tmp_db REDIS_URL=redis://localhost:6379/0 PYTHONPATH=apps/api .venv/bin/alembic upgrade head
```

Depois implementar API/React para criação de OS pela conversa, numeração
concorrente, atribuição, SLA, recepção/triagem, tarefas, timeline pública/
interna e testes E2E. Em seguida atualizar os quatro documentos, fazer commit e
push. A Entrega Vertical 2 permanece aberta.

## Atualização OS - 2026-07-22

A migração `f2c3d4e5a601` e o commit `d160958` entregam OS pela conversa,
numeração transacional, workflow, SLA inicial, recepção/triagem, tarefas,
timeline interna/pública e detalhe React. Testes modulares: 21 aprovados; os
3 legados e 5 frontend permanecem aprovados. Próximo incremento: diagnóstico,
medições, testes técnicos, checklists e conclusão.

## Handoff para nova seção - 2026-07-22

### Estado verificável

Branch `main` está em `202095f docs: record service order operations increment`,
alinhada com `origin/main` no último estado publicado. A árvore local contém
uma alteração deliberadamente iniciada, ainda não commitada, para o próximo
incremento:

- `apps/api/provisao_api/models.py`: modelos `ServiceOrderDiagnosis`,
  `ServiceOrderMeasurement`, `ServiceOrderTechnicalTest`, `ChecklistTemplate`
  e `ServiceOrderChecklist`.
- `migrations/versions/g3d4e5f6a702_technical_records_and_checklists.py`:
  migração candidata, descendente de `f2c3d4e5a601`.

Não há API, testes ou interface publicados para esses modelos. A migração foi
validada localmente em SQLite temporário no ciclo upgrade → downgrade para
`f2c3d4e5a601` → upgrade, e `compileall` passou. Isso valida apenas o schema;
não declarar o incremento concluído.

### Evidências publicadas acumuladas

- Workflow persistente/versionado, editor e execução: `17865b8`, `8cd4676`,
  `a9d9488`, `8fc01e4`.
- CRM completo inicial: `411a2d9`, `3d06aad`, `4d9e760`.
- Catálogos/equipamentos: `20e1b8f`.
- OS, recepção, triagem, tarefas, SLA inicial e timeline: `d160958`, `202095f`.
- Regressões anteriormente aprovadas: backend modular 21, legado 3,
  frontend 5; build Vite/TypeScript, compileall e ciclos Alembic.

### Próximo comando exato

```bash
cd /opt/provisao/site_gestaao_os_orcamentos
git status --short --branch
PYTHONPATH=apps/api .venv/bin/python -m unittest discover -s apps/api/tests -v
```

### Sequência obrigatória de retomada

1. Criar `technical_api.py` tenant-scoped e incluí-lo em `main.py` para
   diagnósticos versionados, medições, testes técnicos, templates/checklists e
   auditoria/timeline.
2. Criar testes backend de draft → revisão → aprovação imutável, nova versão,
   medições, testes, checklist obrigatório e isolamento por organização.
3. Integrar formulários reais na tela React de OS; nenhum botão pode ser apenas
   visual.
4. Implementar conclusão técnica, tarefas obrigatórias, SLA operacional,
   bancada/remoto/campo, visitas, entrega, garantia e retorno.
5. Emitir notificações públicas pela outbox Telegram existente; eventos
   internos permanecem internos.
6. Executar regressões, frontend, build, Compose/smoke e auditoria; atualizar
   os quatro documentos, fazer commits pequenos e publicar quando possível.

### Limitações externas conhecidas

Token Telegram real e domínio/TLS não estão disponíveis; a implementação deve
continuar com Telegram fake e configuração desativada. Push pode depender de
DNS/rede do ambiente. Nenhuma dessas limitações impede o desenvolvimento local.

### Persistência do handoff

As alterações desta documentação e o schema inicial estão no working tree. O
commit não pôde ser criado nesta execução porque `.git/index` está montado como
somente leitura (`Unable to create .git/index.lock`). Preserve os arquivos e
crie o commit assim que o índice estiver gravável; não use `reset` ou `clean`.

## Atualização técnica posterior - 2026-07-22

`technical_api.py` foi integrado ao FastAPI. A revisão candidata `g3d4e5f6a702`
passou o ciclo de migração e há testes para diagnóstico draft/revisão/aprovação,
nova versão, medições, testes e checklist obrigatório. Backend passou 24 testes;
frontend passou 5 testes e build Vite/TypeScript.

A tela de OS possui ações reais para criar e revisar diagnóstico, registrar
medição/teste e aplicar checklist publicado. Ainda faltam conclusão técnica,
bancada/remoto/campo, agenda, entrega, garantia, retorno, notificações públicas
e E2E completo. Faça o commit assim que `.git/index` estiver gravável.

Eventos públicos de entrega, garantia e retorno já reutilizam o outbox Telegram
canônico quando há conversa Telegram vinculada; eventos internos não geram
mensagem externa. A próxima unidade é a interface React dessas operações e o
teste E2E completo com fake Telegram.

## Atualização de atendimento e garantia - 2026-07-22

Foi iniciado o incremento seguinte com `completion_api.py` e a migração
`h4e5f6a7b803`: sessões de bancada/remoto/campo, visitas, entrega/retirada,
garantias e abertura de retorno em nova OS. Testes backend passaram 26/26,
frontend 5/5, build e ciclo Alembic reversível passaram. Ainda faltam telas
React dessas operações, transições finais protegidas, notificações Telegram e
E2E completo. Preserve os arquivos locais antes de retomar.
