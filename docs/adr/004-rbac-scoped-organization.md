# ADR 004 - RBAC persistente com escopo de organizacao

Data: 2026-07-22

Usuarios pertencem a uma empresa; papeis, unidades e equipes tambem sao
isolados por empresa. Permissoes sao conferidas no backend e toda negacao gera
auditoria. O papel `admin` e reservado ao bootstrap administrativo; demais
papeis recebem uma lista explicita de permissoes.
