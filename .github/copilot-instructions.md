<!-- Arquivo gerenciado pelo ai-switch (fonte unica: AGENTS.md). Para atualizar, rode: ai-switch sync. -->

# Ponto de partida universal para IAs

Projeto: site_gestaao_os_orcamentos
Diretorio: /opt/provisao/site_gestaao_os_orcamentos

Este projeto e operado por varias IAs (Claude, Codex, Gemini, Antigravity e outras). Para que
todas comecem exatamente no mesmo ponto, mesmo na primeira vez que abrem o
codigo, siga este protocolo antes de qualquer alteracao.

## 1. Contexto
- Trabalhe somente dentro de `/opt/provisao/site_gestaao_os_orcamentos`.
- Nao altere nem copie outros projetos em /opt/provisao sem autorizacao explicita.

## 2. Leitura obrigatoria antes de alterar qualquer arquivo (nesta ordem)
1. README.md
2. PROJECT_CONTEXT.md
3. DEVELOPMENT_LOG.md
4. HANDOFF_AI.md

Esses arquivos .md sao a fonte de verdade do projeto: objetivo, estado atual,
fases concluidas, fase em andamento, arquivos importantes, testes ja executados,
pendencias e proximo passo recomendado. Em caso de conflito, o documento mais
recente (veja datas no DEVELOPMENT_LOG.md e no HANDOFF_AI.md) tem prioridade.

## 3. Como trabalhar
- Continue exatamente do ponto documentado; nao refaca fases ja concluidas.
- Trabalhe por fases pequenas e verificaveis.
- Teste antes de declarar qualquer fase concluida; nao declare o sistema
  finalizado sem evidencias.
- Nunca exponha tokens, segredos ou credenciais, e nao os altere.

## 4. Ao terminar qualquer alteracao relevante
Atualize README.md, DEVELOPMENT_LOG.md, HANDOFF_AI.md e PROJECT_CONTEXT.md com o
que mudou e registre o proximo passo recomendado para a proxima IA.

## 5. Primeiro comando
```
pwd
```
