# Especificação: Recuperação

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `indexacao.md` (v1.0), `banco-vetorial.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Definir a estratégia de recuperação de chunks relevantes para uma consulta do usuário: busca vetorial, filtros por metadados, busca híbrida (se justificada), deduplicação, expansão de consultas e diversidade de resultados — antes do re-ranking (`reranking.md`) e construção de contexto (`construcao-contexto.md`).

---

## 2. Escopo

Cobre a implementação do `Retriever` (porta definida em `arquitetura.md`). Não cobre o re-ranking dos resultados (etapa separada, `reranking.md`) nem a montagem final do contexto (`construcao-contexto.md`).

---

## 3. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-REC-01 | Realizar busca vetorial (similaridade de cosseno) sobre os embeddings indexados no Qdrant, retornando os top-K chunks mais similares à query. |
| RF-REC-02 | Suportar filtros por metadados na busca (ex.: restringir por `categoria`, `documento_id`, `data`), combinados com a busca vetorial. |
| RF-REC-03 | Avaliar e, se justificado por benchmark, implementar **busca híbrida** (combinação de busca vetorial + busca lexical/keyword, ex.: BM25) para capturar casos onde termos exatos (nomes próprios, códigos, siglas técnicas) são mais bem recuperados por busca lexical do que semântica. |
| RF-REC-04 | Deduplicar resultados: se múltiplos chunks muito similares entre si (ex.: overlap de conteúdo entre chunk-pai e chunk-filho) forem recuperados, reduzir redundância antes de passar ao re-ranking. |
| RF-REC-05 | Avaliar expansão de consultas (query expansion) apenas se o benchmark demonstrar ganho — por exemplo, gerar variações da pergunta original para aumentar recall, mas com cautela quanto ao custo computacional adicional. |
| RF-REC-06 | Garantir diversidade de resultados quando apropriado (evitar que os top-K resultados venham todos do mesmo documento/seção, quando isso prejudicar a cobertura da resposta). |
| RF-REC-07 | Registrar, para cada consulta, quais chunks foram recuperados e com quais scores, propagando o `trace_id` (RF-10 da visão geral). |

---

## 4. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-REC-01 | Toda estratégia de recuperação (híbrida, expansão de consulta, diversidade) deve ser **mensurada via benchmark** antes de ser adotada definitivamente — nenhuma delas é assumida como benéfica por padrão (conforme diretriz explícita do projeto). |
| RNF-REC-02 | Latência de recuperação deve ser compatível com uso interativo, especialmente relevante se busca híbrida ou expansão de consulta adicionarem etapas computacionais. |
| RNF-REC-03 | A estratégia de recuperação deve ser configurável (habilitar/desabilitar híbrida, expansão, deduplicação) para facilitar comparação A/B via benchmark. |

---

## 5. Dependências

* `VectorStore` (Qdrant embutido) com índice populado (`indexacao.md`).
* Modelo de embedding para vetorizar a query do usuário (mesmo modelo usado na indexação, `embeddings.md`).
* Golden set de perguntas de referência (`testes.md`) para medir Precision@K, Recall@K, MRR, nDCG de cada estratégia.
* Biblioteca de busca lexical (ex.: BM25 via `rank_bm25` ou similar) **caso** a busca híbrida seja adotada após benchmark.

---

## 6. Processo de Decisão sobre Busca Híbrida e Expansão de Consulta

Conforme diretriz do projeto ("busca híbrida quando justificar ganhos", "expansão de consultas quando vantajosa"), nenhuma dessas técnicas é adotada por padrão. Processo:

1. Implementar primeiro a busca vetorial pura + filtros de metadados + deduplicação (baseline).
2. Medir Precision@K, Recall@K, MRR, nDCG do baseline no golden set.
3. Implementar busca híbrida (vetorial + BM25) como variante experimental.
4. Comparar métricas: se a busca híbrida gerar ganho relevante (a definir threshold mínimo, ex.: +5% em Recall@K), adotá-la; caso contrário, manter apenas busca vetorial para reduzir complexidade e latência.
5. Repetir processo análogo para expansão de consultas, se houver tempo/prioridade para essa investigação.
6. Documentar a decisão final (adotar ou não cada técnica) em ADR com evidências do benchmark.

---

## 7. Critérios de Aceitação

* [ ] Busca vetorial pura retorna corretamente os top-K chunks mais similares à query.
* [ ] Filtros por metadados funcionam corretamente combinados com a busca vetorial.
* [ ] Deduplicação reduz redundância mensurável nos resultados (validado com casos de teste com overlap conhecido).
* [ ] Decisão sobre adoção de busca híbrida está documentada com evidências de benchmark (adotada ou descartada, ambas são resultados válidos).
* [ ] Cada consulta é rastreável: chunks recuperados + scores + `trace_id` registrados.

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Busca híbrida mal calibrada (peso errado entre vetorial e lexical) pode piorar resultados em vez de melhorar | Médio | Processo de benchmark obrigatório antes de adotar (seção 6); não adotar se não houver ganho claro |
| Deduplicação agressiva pode remover chunks legitimamente complementares (não apenas redundantes) | Médio | Calibrar threshold de similaridade para deduplicação com cuidado, validado no golden set |
| Expansão de consultas pode introduzir ruído se as variações geradas divergirem muito da intenção original | Médio | Adotar apenas se benchmark mostrar ganho líquido; manter simples (ex.: sinônimos) se adotado |

---

## 9. Alternativas Avaliadas

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| Apenas busca vetorial | Simples, rápida, geralmente boa para similaridade semântica | Pode falhar em termos exatos (siglas, códigos técnicos comuns em docs corporativos) | Baseline obrigatório, ponto de partida |
| Busca híbrida (vetorial + BM25) | Melhor para termos exatos, potencial ganho de recall | Complexidade adicional, latência adicional | A adotar **apenas se benchmark confirmar ganho** (RNF-REC-01) |

---

## 10. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Busca vetorial pura como baseline obrigatório antes de qualquer técnica adicional | Estabelece linha de base mensurável para comparação (RNF-REC-01) | Proposto |
| Nenhuma técnica adicional (híbrida, expansão) é adotada sem evidência de benchmark | Alinhado à diretriz explícita do projeto de nunca assumir ganhos sem medição | Proposto |
| `Retriever` configurável via flags/parâmetros para facilitar comparação A/B | Permite testar variantes sem duplicar código | Proposto |

---

## 11. Estratégia de Testes

* **Unitários:** busca vetorial, aplicação de filtros, deduplicação, testados isoladamente.
* **Integração:** indexação → recuperação, validando que os chunks corretos são retornados para queries de teste conhecidas.
* **Benchmark (crítico):** golden set usado para comparar baseline vs. variantes (híbrida, expansão), conforme processo da seção 6.
* **Regressão:** queries de teste fixas devem retornar resultados estáveis entre execuções (dado o mesmo índice).

---

## 12. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado e aprovado na mesma revisão (v1.0) | Nenhuma pendência bloqueante; decisão sobre busca híbrida/expansão de consulta fica condicionada a benchmark durante implementação, conforme processo da seção 6 |

---

**Próximo passo:** avançar para `reranking.md`, detalhando a estratégia de re-ranking dos resultados recuperados.
