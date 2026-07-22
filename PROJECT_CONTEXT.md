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

- Fase atual: Fundacao da refatoracao para Fase A/B.
- Legado preservado: `app/server.py`, frontend estatico e SQLite continuam
  disponiveis somente como referencia/backup.
- Nova aplicacao: `apps/api/`, com Compose em `docker-compose.yml`.
- Persistencia alvo: PostgreSQL; SQLite ainda nao foi migrado.
- Documentacao de produto: `docs/product/MASTER_BLUEPRINT.md`.
- Execucao e limites: `docs/operations/LOCAL_RUNBOOK.md`.
- Decisao de arquitetura do corte: `docs/adr/001-stdlib-mvp.md`.

## Proximo passo recomendado

Proximo incremento recomendado: concluir migracoes Alembic e importador
SQLite, depois implementar os modulos de identidade/organizacao e conversas.
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
