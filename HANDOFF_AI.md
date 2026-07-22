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
3. Concluir Alembic e migracao SQLite para PostgreSQL antes de uso multiusuario real.
4. Manter Telegram como gateway sem acesso direto ao banco.
5. Manter IA local desacoplada das transacoes e com saidas validadas por schema.
6. Nunca tratar o endpoint demonstrativo Telegram como webhook de producao sem
   autenticacao do gateway, criptografia de segredos e rate limiting.

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
