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

## Proximo passo recomendado

Proximo incremento recomendado: implementar o gateway Telegram real como
adaptador do serviço canônico, incluindo criptografia de token, validação de
webhook, download de mídia e envio pelo outbox.
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
