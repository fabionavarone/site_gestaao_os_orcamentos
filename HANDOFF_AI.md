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
