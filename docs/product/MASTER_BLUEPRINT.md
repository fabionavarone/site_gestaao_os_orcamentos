# Master Blueprint de Produto e Desenvolvimento - Provisao Manager

Versao: 3.0 - Multimodal e Omnichannel
Status: especificacao mestre para implementacao
Produto: plataforma inteligente de atendimento e gestao completa de assistencia tecnica
Empresa inicial: Provisao Sistemas

Este documento consolida o blueprint recebido em 2026-07-22 para orientar a evolucao do projeto. Em caso de conflito com documentos locais mais recentes, prevalece a regra de precedencia abaixo.

## Regra de Precedencia

1. Seguranca, integridade de dados e rastreabilidade.
2. Regras de negocio aprovadas.
3. Requisitos funcionais deste blueprint.
4. Restricoes de infraestrutura.
5. Conveniencia tecnica ou preferencia de biblioteca.

## Visao

O Provisao Manager deve ser uma plataforma centralizada para receber, interpretar, direcionar e gerenciar atendimentos de assistencia tecnica por Telegram e Web.

O produto nao deve ser apenas um chatbot ou gerador de orcamentos. A conversa e o centro do atendimento; a ordem de servico e o centro da execucao tecnica quando aplicavel.

Objetivos principais:

- receber texto, imagem, audio e documentos pelo Telegram e pela Web;
- converter cada entrada em evento canonico, independente do canal;
- identificar usuario, cliente, equipamento, intencao, urgencia e contexto;
- selecionar fluxo adequado, solicitar dados faltantes e registrar atendimento estruturado;
- abrir e acompanhar ordens de servico, diagnostico, orcamento, aprovacao, reparo, entrega, garantia, cobranca e historico tecnico;
- manter comunicacao rastreavel com cliente;
- gerar documentos versionados em PDF;
- produzir indicadores tecnicos, comerciais, financeiros e operacionais;
- usar IA local como camada de interpretacao, classificacao, extracao e assistencia conversacional.

## Principios

- Todo equipamento deve possuir identidade e historico.
- Toda alteracao relevante deve possuir autor, data e justificativa.
- Mensagens nao substituem dados estruturados.
- Documentos emitidos sao versoes imutaveis.
- Permissoes seguem menor privilegio.
- O sistema deve continuar operando quando a IA estiver indisponivel.
- Telegram e Web sao canais de primeira classe sobre o mesmo nucleo de negocio.
- Nenhum canal deve implementar regras de negocio em paralelo.
- Toda entrada multimodal deve ser normalizada, correlacionada e auditavel.
- Baixa confianca deve resultar em confirmacao ou transferencia humana.

## Escopo Inicial

Incluido no escopo progressivo:

- caixa de entrada omnichannel;
- interpretacao multimodal;
- motor configuravel de fluxos, regras, estados e transicoes;
- usuarios, papeis, empresas, unidades, equipes, bots e vinculos Telegram;
- CRM operacional;
- cadastro e rastreamento de equipamentos;
- ordens de servico internas e externas;
- triagem, diagnostico, orcamento, aprovacao e reparo;
- pecas, estoque, agenda, financeiro operacional e garantia;
- documentos corporativos;
- portal do cliente;
- dashboards, relatorios e base de conhecimento;
- automacao com IA local.

Fora do MVP:

- contabilidade completa;
- emissao fiscal nativa sem integracao homologada;
- folha de pagamento;
- marketplace de pecas;
- aplicativo movel nativo completo;
- construtor visual BPMN avancado;
- diagnostico ou decisoes sensiveis totalmente autonomas;
- integracoes nao autorizadas com fabricantes, fiscais ou financeiras.

## Publicos e Permissoes

O sistema deve atender publicos internos e externos com experiencias e permissoes distintas.

Perfis internos:

- diretor/administrador;
- atendimento/recepcao;
- comercial;
- supervisor tecnico;
- tecnico interno;
- tecnico de campo;
- estoque/compras;
- financeiro;
- auditor/consulta.

Perfis externos:

- cliente pessoa fisica ou juridica;
- gestor de cliente empresarial;
- parceiro ou tecnico terceirizado;
- fornecedor autorizado.

Modelo obrigatorio: RBAC com escopo, combinando papel, empresa, unidade, equipe, ordem atribuida, propriedade do registro, alcada financeira e restricoes por campo sensivel.

Requisitos:

- permissoes verificadas no backend;
- frontend nunca e unica barreira;
- sessoes revogaveis;
- registro de acesso negado;
- clientes externos isolados por empresa/tenant;
- impersonacao administrativa somente com auditoria explicita.

## Nucleo Multimodal

Toda entrada deve ser convertida para envelope canonico antes da interpretacao.

Envelope conceitual:

```json
{
  "event_id": "ulid",
  "channel": "telegram|web",
  "bot_id": "uuid|null",
  "conversation_id": "uuid",
  "external_chat_id": "string|null",
  "external_message_id": "string|null",
  "sender": {
    "external_id": "string|null",
    "user_id": "uuid|null",
    "customer_contact_id": "uuid|null",
    "display_name": "string|null"
  },
  "message_type": "text|voice|audio|image|document|command|callback|system",
  "text": "string|null",
  "caption": "string|null",
  "file_ids": ["uuid"],
  "reply_to_message_id": "uuid|null",
  "received_at": "datetime",
  "metadata": {},
  "idempotency_key": "string"
}
```

Pipeline obrigatorio:

1. Receber evento do canal.
2. Validar origem, bot, assinatura, tamanho, tipo e duplicidade.
3. Identificar ou criar conversa.
4. Resolver identidade e permissoes do remetente.
5. Armazenar conteudo original.
6. Pre-processar midia sem substituir original.
7. Transcrever audio quando necessario.
8. Interpretar imagem ou documento quando aplicavel.
9. Consolidar representacao textual e estruturada.
10. Classificar intencao, entidades, prioridade, risco e confianca.
11. Consultar estado da conversa e regras de roteamento.
12. Selecionar fluxo ativo e versao.
13. Executar proxima etapa permitida ou solicitar confirmacao.
14. Responder no canal de origem e atualizar caixa de entrada Web.
15. Registrar decisoes, ferramentas, resultado e latencia.

Falhas de IA nao podem apagar mensagem nem impedir atendimento manual.

## Intencoes Iniciais

O catalogo deve ser versionado e extensivel. MVP minimo:

- iniciar novo atendimento;
- solicitar reparo ou diagnostico;
- cadastrar ou identificar equipamento;
- enviar evidencia ou documento;
- consultar andamento de OS;
- solicitar orcamento;
- aprovar ou rejeitar orcamento;
- informar pagamento;
- solicitar visita tecnica;
- solicitar laudo ou relatorio;
- relatar retorno em garantia;
- falar com atendente;
- suporte de acesso;
- comando administrativo autorizado;
- assunto nao reconhecido;
- conteudo suspeito, abusivo ou fora da politica.

## Entidades e Confianca

Entidades extraidas devem armazenar valor, origem e confianca. O sistema deve diferenciar:

- informado pelo usuario;
- observado em imagem ou documento;
- inferido pela IA;
- confirmado por cadastro existente;
- validado por usuario ou funcionario.

Limiares iniciais:

- alta confianca: encaminhar automaticamente somente fluxo de baixo risco;
- confianca intermediaria: pedir confirmacao;
- baixa confianca: perguntar objetivamente ou enviar para triagem humana;
- acao sensivel: exigir regra deterministica, permissao e confirmacao humana quando aplicavel.

## Motor de Fluxos

Fluxos devem ser registros versionados, persistentes, testaveis e publicaveis. Nao podem existir apenas em prompts.

Cada fluxo deve definir:

- identificador e versao;
- intencao de entrada;
- publico e permissoes;
- estado inicial;
- etapas;
- campos obrigatorios e opcionais;
- validacoes;
- acoes de dominio;
- condicoes de transicao;
- timeouts e lembretes;
- criterios de conclusao;
- condicoes de transferencia humana;
- fallback;
- politica de auditoria.

Tipos de etapa do MVP:

- mensagem;
- pergunta de texto;
- selecao de opcao;
- solicitacao de arquivo, foto ou audio;
- confirmacao;
- consulta de dado;
- criacao ou atualizacao de rascunho;
- chamada de ferramenta autorizada;
- espera por evento;
- atribuicao a fila ou atendente;
- encerramento.

## Ordem de Servico

Estados principais:

- `draft`;
- `awaiting_receipt`;
- `received`;
- `triage`;
- `diagnosis`;
- `awaiting_budget`;
- `awaiting_customer_approval`;
- `approved`;
- `rejected`;
- `awaiting_parts`;
- `repair_in_progress`;
- `quality_test`;
- `technical_hold`;
- `customer_hold`;
- `financial_hold`;
- `ready_for_delivery`;
- `delivered`;
- `closed`;
- `cancelled`;
- `warranty_return`;
- `no_repair_condition`.

Regras obrigatorias:

- OS nao vai para reparo sem aprovacao, salvo autorizacao interna registrada.
- OS nao vai para entrega sem checklist tecnico aprovado.
- OS nao e encerrada sem motivo, responsavel e documentacao minima.
- Orcamento rejeitado nao apaga diagnostico ou historico.
- Reabertura cria evento de auditoria.
- Retorno em garantia referencia OS original.
- Mudanca manual fora do fluxo exige permissao especial e justificativa.

## Modulos Funcionais

Modulos previstos:

- identidade e organizacao;
- canais, bots, conversas e automacao;
- clientes e CRM;
- equipamentos e ativos;
- recepcao e triagem;
- ordens de servico;
- tecnico, diagnostico e qualidade;
- orcamentos e aprovacoes;
- estoque e compras;
- agenda e equipes;
- financeiro operacional;
- documentos e arquivos;
- comunicacao omnichannel;
- portal do cliente;
- dashboards e relatorios;
- conhecimento tecnico;
- IA e auditoria.

## IA Local

A IA e central para interpretacao multimodal, mas desacoplada da integridade transacional.

Casos prioritarios:

- classificar intencao;
- consolidar texto, transcricao e conteudo visual;
- transcrever audio;
- extrair dados de etiquetas e documentos;
- sugerir preenchimento de OS;
- resumir historico;
- estruturar sintomas;
- sugerir checklist;
- redigir rascunhos de orcamento e laudo;
- localizar conhecimento autorizado;
- identificar inconsistencias.

Casos proibidos sem validacao humana:

- concluir causa tecnica definitiva;
- aprovar orcamento;
- conceder desconto;
- dar baixa em pagamento;
- alterar estoque;
- encerrar OS;
- emitir laudo final;
- enviar comunicacao juridica ou acusatoria;
- excluir registros;
- compartilhar dados de outro cliente;
- executar comandos livres no servidor.

Configuracao obrigatoria:

- `LOCAL_LLM_TEXT_MODEL`;
- `LOCAL_LLM_VISION_MODEL`;
- `LOCAL_STT_MODEL`;
- `LOCAL_TTS_VOICE`;
- `LOCAL_EMBEDDING_MODEL`.

Toda saida estruturada deve ser validada por schema tipado, preferencialmente Pydantic.

## Arquitetura Tecnica

Estrategia inicial: monolito modular, com processos separados apenas por necessidade operacional.

Componentes implantaveis previstos:

- `reverse-proxy`;
- `frontend-web`;
- `backend-api`;
- `worker`;
- `scheduler`;
- `postgres`;
- `redis`;
- `ollama`;
- `ai-worker`;
- `conversation-worker`;
- `telegram-bot`;
- `backup`;
- `monitoring`.

Stack recomendada:

- backend: Python, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, Jinja2, WeasyPrint, Redis;
- frontend: React, Vite, TypeScript, TailwindCSS, TanStack Query ou equivalente, React Hook Form ou equivalente;
- IA local: Ollama ou runtime homologado, faster-whisper, Piper opcional, Pillow;
- infraestrutura: Docker Engine, Docker Compose, Nginx, PostgreSQL, Redis, armazenamento local abstraido.

Restricoes de producao inicial:

- 4 vCPUs;
- 16 GB RAM;
- 200 GB NVMe;
- IA externa proibida por padrao;
- dados e arquivos armazenados localmente por padrao.

## Estrutura-Alvo do Monorepo

```text
apps/
  api/
  web/
  worker/
  ai-worker/
  conversation-worker/
  telegram-bot/
  scheduler/
packages/
  domain/
  application/
  infrastructure/
  contracts/
  document-templates/
  shared/
migrations/
infra/
tests/
docs/
scripts/
```

## Banco de Dados

Entidades principais previstas:

- `users`, `roles`, `permissions`, `user_roles`, `companies`, `branches`, `teams`, `sessions`;
- `channel_bots`, `telegram_accounts`, `telegram_user_bindings`, `conversations`, `conversation_messages`, `workflow_definitions`, `workflow_versions`, `intents`, `routing_rules`;
- `customers`, `customer_contacts`, `customer_addresses`;
- `equipment`, `equipment_categories`, `equipment_identifiers`;
- `service_orders`, `service_order_status_history`, `service_order_events`;
- `diagnostics`, `diagnostic_tests`, `technical_reviews`, `quality_checks`;
- `budgets`, `budget_versions`, `budget_items`, `budget_approvals`;
- `parts`, `stock_locations`, `stock_movements`, `stock_reservations`;
- `receivables`, `payment_installments`, `payments`;
- `files`, `file_versions`, `document_templates`, `generated_documents`;
- `warranties`, `warranty_claims`;
- `ai_jobs`, `ai_interpretations`, `prompt_versions`, `knowledge_documents`;
- `audit_logs`, `security_events`, `outbox_events`.

Convencoes:

- UUID ou ULID;
- timestamps em UTC;
- `company_id` onde adequado;
- migracoes obrigatorias;
- constraints para invariantes importantes;
- registros financeiros, estoque e auditoria nao devem ser apagados.

## API, Eventos e Jobs

Requisitos:

- prefixo `/api/v1`;
- OpenAPI gerada;
- autenticacao consistente;
- paginacao, filtros e ordenacao controlados;
- idempotencia em operacoes criticas;
- optimistic locking quando relevante;
- codigo de erro estavel;
- correlation ID;
- rate limiting em rotas sensiveis;
- health e readiness separados.

Jobs para:

- PDF;
- imagem;
- transcricao;
- IA;
- notificacoes;
- miniaturas;
- importacao/exportacao;
- conhecimento;
- backup;
- indicadores;
- fluxo conversacional.

Eventos de dominio relevantes devem usar outbox.

## Seguranca, Privacidade e Auditoria

Obrigatorio:

- secrets fora do repositorio;
- tokens de bots criptografados em repouso e nunca retornados ao navegador;
- validacao de upload;
- protecao contra path traversal;
- queries parametrizadas;
- HTML de entrada sanitizado;
- containers sem privilegios desnecessarios;
- banco nao exposto publicamente;
- LGPD: minimizacao, finalidade, consentimento quando aplicavel, retencao e protecao de documentos;
- auditoria para login, permissao, OS, diagnostico, orcamento, desconto, estoque, financeiro, documentos, downloads e decisoes com IA.

## Telegram

O bot e gateway do dominio, sem regras de negocio paralelas e sem acesso direto ao banco.

Capacidades:

- receber texto, voz, audio, foto, documento, comando e callback;
- identificar usuario vinculado ou iniciar identificacao segura;
- iniciar e continuar fluxos;
- criar rascunhos autorizados;
- consultar status autorizado;
- adicionar evidencias;
- apresentar botoes;
- transferir para humano;
- enviar documentos liberados.

Administracao Web:

- cadastrar bot;
- inserir/substituir token de forma segura;
- habilitar webhook;
- testar credenciais;
- configurar comandos, menus, allowlist, horario, filas e regras;
- consultar saude e falhas;
- rotacionar segredo;
- revogar vinculos.

## Documentos

Documentos previstos:

- protocolo de entrada;
- ordem de servico;
- orcamento;
- laudo tecnico;
- relatorio de visita;
- termo de retirada sem reparo;
- termo de descarte;
- checklist de testes;
- comprovante de entrega;
- termo de garantia;
- recibo simples quando permitido;
- relatorio gerencial.

Fluxo:

1. Reunir dados autorizados.
2. Validar schema.
3. Criar snapshot.
4. Selecionar template e versao.
5. Renderizar HTML.
6. Gerar PDF em job.
7. Calcular hash.
8. Armazenar arquivo.
9. Criar registro imutavel.
10. Liberar conforme permissao.

## Roadmap

Fase 0 - Descoberta e fundacao:

- mapear processo real;
- definir responsaveis e alcadas;
- coletar documentos atuais;
- definir categorias, estados e SLA;
- criar glossario;
- validar politica de dados e integracoes;
- medir hardware com modelos locais;
- gerar matriz de permissoes, modelo de dados inicial, backlog, ADRs principais e criterios do MVP.

Fase 1 - Identidade, canais e conversas:

- autenticacao Web;
- usuarios, papeis, empresas, unidades e equipes;
- gestao segura de bot Telegram;
- vinculo Telegram;
- recebimento e envio de texto;
- mensagens canonicas;
- conversas, participantes e timeline;
- caixa de entrada Web;
- atendimento humano;
- idempotencia, auditoria, fila basica, anexos, healthchecks e backup.

Criterio de saida da Fase 1:

Uma mensagem enviada ao Telegram deve aparecer na Web, poder ser assumida por atendente e receber resposta pelo mesmo bot, com identidade, auditoria e sem duplicidade.

Fase 2 - Pipeline multimodal e motor de fluxos.
Fase 3 - Nucleo operacional da assistencia tecnica.
Fase 4 - Diagnostico, orcamento, documentos e garantia.
Fase 5 - Estoque, agenda, financeiro e portais.
Fase 6 - Inteligencia avancada e expansao.

## Criterios de Aceite do MVP

Cenarios obrigatorios:

- entrada por texto no Telegram ate criacao de rascunho ou OS auditada;
- entrada por audio com original preservado, transcricao local e classificacao;
- entrada por imagem com original preservado, derivado para IA e extracao de etiqueta;
- atendimento humano integrado com automacao pausavel;
- gestao completa da assistencia: cliente, equipamento, OS, diagnostico, orcamento, aceite, reparo, estoque, teste, laudo, pagamento, entrega e garantia.

Requisitos nao funcionais:

- API comum abaixo de 1s em condicoes normais, excluindo jobs;
- nenhuma inferencia pesada em request sincrono;
- backup restauravel;
- autorizacao testada;
- interface responsiva;
- IA desligavel por configuracao;
- idempotencia contra updates duplicados;
- metricas de classificacao, confirmacao e transferencia;
- tokens protegidos e rotacionaveis.

## Regras Obrigatorias para Assistentes de Codigo

- Ler este blueprint antes de alterar arquitetura ou dominio.
- Nao criar dependencia externa sem autorizacao.
- Nao adicionar microsservico sem ADR.
- Nao colocar regra de negocio apenas em rota ou componente React.
- Nao acessar banco diretamente pelo bot.
- Nao permitir SQL ou shell livre pela IA.
- Nao retornar sucesso antes da transacao confirmar.
- Nao criar migracao destrutiva sem rollback.
- Nao alterar documento emitido.
- Nao armazenar arquivo apenas pelo nome original.
- Nao criar endpoint sem autorizacao e testes.
- Nao misturar comentario interno com mensagem ao cliente.
- Nao hardcodar modelos, URLs, tokens ou dados da empresa.
- Nao aceitar saida LLM sem schema.
- Nao implementar fluxo critico apenas por prompt.
- Nao ocultar falhas de IA ou jobs.
- Nao apagar registros financeiros, estoque ou auditoria.
- Manter compatibilidade com os limites do servidor.
- Entregar codigo executavel, testes e documentacao.
- Registrar suposicoes e pendencias.
- Normalizar toda entrada de canal antes de processar.
- Nao confiar no `username` do Telegram como identidade.
- Nao expor token ou segredo de bot.
- Implementar idempotencia para updates e mensagens.
- Nao executar acao em estado de conversa incompativel.
- Registrar versao de intencao, fluxo, prompt e modelo em cada decisao.
- Garantir que humano possa assumir e pausar a automacao.

## Pendencias de Negocio

Antes de iniciar codigo funcional da Fase 1, validar ao menos:

- categorias de equipamentos do MVP;
- documentos atuais a reproduzir;
- estados e SLA por tipo de servico;
- matriz de permissoes e alcadas;
- politica de desconto, garantia, abandono e retencao;
- metodo de vinculo com Telegram;
- horario da automacao e atendimento humano;
- filas iniciais;
- catalogo inicial de intencoes com exemplos reais;
- quais fluxos podem criar OS e quais criam apenas rascunho;
- metas minimas de precisao, confirmacao e transferencia.

## Regra Final

O Provisao Manager deve ser construido como plataforma de atendimento inteligente e sistema operacional confiavel para assistencia tecnica.

Telegram e Web devem compartilhar identidade, conversa, estado, fluxo, regras e dados. Nenhum canal pode se tornar sistema paralelo.

A IA local interpreta texto, imagem e audio, extrai informacoes, classifica intencoes e escolhe fluxos permitidos. A verdade operacional permanece em eventos canonicos, dados estruturados, servicos de dominio, permissoes, evidencias e auditoria.
