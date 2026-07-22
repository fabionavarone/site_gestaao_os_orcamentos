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

Dominio, organizacao e canais sobre a base migrada.

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
- núcleo omnichannel persistente: canais, identidades externas, eventos
  deduplicados, inbox, atribuição humana e outbox com retry/dead-letter.

O próximo incremento é o gateway Telegram real configurável, que consumirá o
núcleo omnichannel já persistente. Uploads e anexos continuam pendentes.

## Regras

- Trabalhar somente dentro deste diretorio.
- Nao alterar outros projetos em `/opt/provisao` sem autorizacao explicita.
- Nao copiar arquivos de outros projetos sem autorizacao explicita.
- Ler `docs/product/MASTER_BLUEPRINT.md` antes de alterar arquitetura ou dominio.
