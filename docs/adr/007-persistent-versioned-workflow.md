# ADR 007 - Workflow persistente, versionado e publicável

Data: 2026-07-22

## Decisão

Estados e transições de OS passam a ser registros vinculados a uma versão de
workflow. Uma versão publicada é imutável; mudanças exigem clonagem. Instâncias
continuam ligadas à versão em que começaram. Condições usam somente operadores
declarativos permitidos e ações são despachadas para serviços de aplicação
registrados, sem `eval`, SQL configurável ou execução livre.

A migração `c4f23b1a9d02` cria e publica um workflow padrão por empresa, mapeia
cada OS existente para o estado homônimo e cria exatamente uma instância por
entidade. A numeração de novas OS passa a usar contador transacional por empresa.

## Consequências

- publicação exige grafo com um estado inicial, alcançabilidade e terminais
  coerentes;
- histórico e execução de ações são persistidos separadamente;
- downgrade remove o motor, mas preserva o campo textual de estado e os eventos
  históricos originais da OS;
- módulos técnicos adicionam handlers de domínio sem acoplar SQL ao editor.
