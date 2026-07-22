# Workflow persistente

## Administração

A tela **Workflows** lista definições, versões, estados, transições, condições e
ações. Somente drafts podem ser editados. Use **Validar grafo** antes de
**Publicar**; uma versão publicada somente pode originar uma nova versão por
**Clonar versão**.

Permissões: `workflow.view`, `workflow.manage`, `workflow.publish` e
`workflow.execute`. Transições de OS usam `service_order.transition`.

Condições aceitas: `equals`, `not_equals`, `in`, `not_in`, `exists`,
`greater_than`, `less_than`, `all` e `any`. Não há avaliação de código.

## Migração e rollback

```bash
alembic upgrade c4f23b1a9d02
alembic downgrade 9c30f4a612ef
```

O upgrade cria workflow padrão e instâncias idempotentes por empresa/entidade.
Antes de downgrade em ambiente com execuções novas, faça backup do banco: o
downgrade preserva estados e eventos legados da OS, mas remove configuração e
histórico próprios do motor.

## Verificação

```bash
PYTHONPATH=apps/api .venv/bin/python -m unittest apps.api.tests.test_workflow -v
```

Confirme que nenhuma OS ficou sem instância:

```sql
SELECT count(*) FROM service_orders WHERE workflow_instance_id IS NULL;
```
