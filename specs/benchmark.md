# Especificação: Benchmark

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `testes.md` (v1.0) e todas as demais specs de pipeline
**Data:** 2026-07-04

---

## 1. Objetivo

Implementar o módulo de benchmark automatizado que mede, de forma reproduzível, a qualidade de recuperação, a qualidade de contexto, o desempenho e a qualidade final das respostas — fornecendo a evidência objetiva exigida por todas as decisões técnicas do projeto (tamanho de chunk, modelo de embedding, uso ou não de busca híbrida/re-ranking/expansão de consulta), conforme diretriz central de `visao-geral.md`: **nunca escolher tecnologia por conveniência ou popularidade, sempre por benchmark.**

---

## 2. Escopo

Cobre a implementação do `BenchmarkRunner` (porta definida em `arquitetura.md`) e a agregação de todas as métricas já mencionadas nas specs anteriores em um módulo coeso, executável via `/v1/benchmark/run` (`api.md`). Não cobre a criação do golden set em si (`testes.md`), apenas seu uso para medição.

---

## 3. Métricas de Recuperação

| Métrica | Definição |
|---------|-----------|
| Precision@K | Proporção de chunks relevantes entre os top-K recuperados |
| Recall@K | Proporção de chunks relevantes (do ground truth) que foram efetivamente recuperados nos top-K |
| MRR (Mean Reciprocal Rank) | Média do inverso da posição do primeiro chunk relevante recuperado |
| nDCG (Normalized Discounted Cumulative Gain) | Qualidade da ordenação dos resultados, considerando posição e relevância graduada |
| Hit Rate | Proporção de perguntas para as quais pelo menos um chunk relevante foi recuperado |

## 4. Métricas de Contexto

| Métrica | Definição |
|---------|-----------|
| Quantidade média de tokens enviados | Tokens usados no contexto final por consulta (deve respeitar o orçamento de `construcao-contexto.md`) |
| Taxa de redundância entre chunks | Medida de sobreposição/similaridade entre os chunks incluídos no mesmo contexto |
| Percentual de conteúdo irrelevante | Proporção do contexto que não contribui para a resposta correta (estimado comparando com o ground truth) |
| Cobertura da resposta correta | Se toda a informação necessária para responder corretamente está presente no contexto montado |

## 5. Métricas de Desempenho

| Métrica | Definição |
|---------|-----------|
| Tempo médio de indexação | Por documento, medido em `indexacao.md` |
| Tempo médio de recuperação | Latência da etapa de busca (`recuperacao.md`) |
| Latência total da consulta | Ponta a ponta, do recebimento da pergunta até a resposta da LLM |
| Consumo de memória | VRAM/RAM utilizada durante indexação e consulta |
| Consumo de armazenamento | Tamanho do índice vetorial + armazenamento de documentos originais |

## 6. Métricas de Qualidade Final (Grounding e Resposta)

| Métrica | Definição |
|---------|-----------|
| Fidelidade ao contexto (grounding) | A resposta contém apenas informação presente no contexto fornecido, sem invenção |
| Taxa de admissão de desconhecimento | Para perguntas negativas do golden set, se a LLM corretamente admite não saber |
| Comparação entre configurações | Respostas usando contexto completo vs. reduzido, diferentes estratégias de chunking/embeddings/recuperação — conforme exigido em `visao-geral.md` |

---

## 7. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-BENCH-01 | Executar o golden set completo (`testes.md`) contra a configuração atual do sistema, calculando todas as métricas das seções 3-6. |
| RF-BENCH-02 | Permitir execução de benchmark com configurações alternativas (ex.: tamanho de chunk diferente, modelo de embedding diferente) para comparação lado a lado, sem exigir reimplantação completa do sistema. |
| RF-BENCH-03 | Persistir resultados de cada execução de benchmark (histórico), consultável via `/v1/benchmark/results` (`api.md`). |
| RF-BENCH-04 | Gerar um relatório comparativo legível (ex.: tabela markdown ou JSON estruturado) entre execuções de benchmark, facilitando a tomada de decisão documentada em ADRs. |
| RF-BENCH-05 | Para a métrica de grounding (seção 6), usar uma abordagem de verificação automatizada (ex.: verificar se afirmações da resposta são sustentadas pelo contexto) complementada por amostragem de revisão humana periódica, dado que verificação 100% automatizada de grounding é imperfeita. |

---

## 8. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-BENCH-01 | O benchmark deve ser executável sob demanda (via API) e também agendável (ex.: rodar automaticamente após mudanças significativas de configuração), mas não é necessário rodar continuamente em produção dado o porte do projeto. |
| RNF-BENCH-02 | Resultados devem ser reproduzíveis: a mesma configuração e o mesmo golden set devem produzir os mesmos resultados (exceto por aspectos não determinísticos da LLM, mitigados por `temperature = 0.0` já confirmado em `llm.md`). |
| RNF-BENCH-03 | O módulo de benchmark não deve ser um componente descartável de teste manual, mas parte permanente e versionada da plataforma, dado seu papel central na metodologia do projeto. |

---

## 9. Dependências

* Golden set (`testes.md`, 30 perguntas).
* Todos os módulos do pipeline implementados e configuráveis (parsing até LLM).
* `/v1/benchmark/run` e `/v1/benchmark/results` (`api.md`).

---

## 10. Critérios de Aceitação

* [ ] Todas as métricas das seções 3-6 são calculadas automaticamente ao rodar o benchmark.
* [ ] É possível comparar duas configurações diferentes lado a lado (ex.: tamanho de chunk A vs. B) via relatório gerado pelo benchmark.
* [ ] Histórico de execuções de benchmark é persistido e consultável.
* [ ] Métrica de grounding está implementada com verificação automatizada + processo de amostragem para revisão humana periódica.
* [ ] Resultados são reproduzíveis dado o mesmo golden set e configuração (considerando `temperature = 0.0`).

---

## 11. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Verificação automatizada de grounding é imperfeita (pode haver falsos positivos/negativos) | Médio | Complementar com amostragem de revisão humana periódica (RF-BENCH-05), não confiar 100% na automação para essa métrica específica |
| Golden set de 30 perguntas pode não capturar toda a variabilidade do corpus real ao longo do tempo | Médio | Expandir o golden set iterativamente (já indicado em `testes.md`); tratar decisões marginais com cautela |
| Benchmark pode se tornar caro computacionalmente se rodado com muita frequência (compete por GPU com uso real do sistema) | Baixo | Rodar sob demanda / antes de releases, não continuamente em produção (RNF-BENCH-01) |

---

## 12. Alternativas Avaliadas

*Não há alternativas arquiteturais relevantes — o módulo de benchmark é um requisito central e explícito do projeto (`visao-geral.md`), não uma escolha entre opções concorrentes. A única decisão prática é como medir grounding de forma automatizada (seção 7, RF-BENCH-05), para a qual se propõe uma abordagem híbrida (automatizada + amostragem humana), por ser mais viável que exigir revisão humana de 100% das execuções.*

---

## 13. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Benchmark como módulo permanente e versionado, não script descartável | Papel central na metodologia do projeto; decisões técnicas dependem dele continuamente, não apenas na fase inicial | Proposto |
| Grounding medido via verificação automatizada + amostragem de revisão humana | Equilíbrio entre viabilidade prática e confiabilidade da métrica mais crítica para confiança na plataforma | Proposto |
| Benchmark executável sob demanda, não contínuo em produção | Evita competição desnecessária por GPU com o uso real do sistema | Proposto |

---

## 14. Estratégia de Testes

* **Unitários:** cálculo de cada métrica (Precision@K, Recall@K, MRR, nDCG, etc.) testado com casos conhecidos/calculados manualmente.
* **Integração:** execução completa do benchmark contra o golden set, validando que o relatório final é gerado corretamente.
* **Meta-teste:** o próprio módulo de benchmark deve ser testado quanto à reprodutibilidade (mesma entrada, mesma saída).

---

## 15. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado e aprovado na mesma revisão (v1.0) | Consolida decisões já estabelecidas nas 17 especificações anteriores |
| 2026-07-04 | Usuário optou por **não iniciar a implementação ainda** | Todas as 18 especificações permanecem aprovadas e documentadas; implementação fica para uma fase futura, a critério do usuário |

---

**Status do projeto:** fase de especificação (Spec-Driven Development) **concluída**. As 18 especificações estão aprovadas e disponíveis em `/specs`. A implementação não foi iniciada nesta sessão, por escolha explícita do usuário — pode ser retomada a qualquer momento, seguindo a ordem do pipeline já documentada (ingestão → parsing → normalização → enriquecimento → chunking → embeddings → banco vetorial → indexação → recuperação → re-ranking → construção de contexto → LLM → API → observabilidade → testes → benchmark), com testes e documentação contínua, conforme o processo obrigatório definido em `visao-geral.md`.
