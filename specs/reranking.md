# Especificação: Re-ranking

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `recuperacao.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Reordenar os chunks retornados pelo `Retriever` por relevância real à query, corrigindo imprecisões da busca vetorial pura (que otimiza por similaridade de embedding, nem sempre perfeitamente alinhada à relevância real da resposta) — etapa crítica para maximizar a qualidade do contexto final entregue a modelos de 4B–9B parâmetros.

---

## 2. Escopo

Cobre a implementação do `Reranker` (porta definida em `arquitetura.md`), que recebe os top-N candidatos do `Retriever` e produz uma lista reordenada (e possivelmente reduzida a top-K) para a `construcao-contexto.md`. Não cobre a busca inicial (`recuperacao.md`) nem a montagem final do contexto.

---

## 3. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-RANK-01 | Receber os top-N chunks candidatos (N > K final desejado) do `Retriever` e reordená-los por um modelo/método de re-ranking mais preciso que a similaridade vetorial pura. |
| RF-RANK-02 | Retornar os top-K chunks finais (K configurável) após o re-ranking, para uso em `construcao-contexto.md`. |
| RF-RANK-03 | O re-ranker deve rodar localmente (sem dependência de API externa), consistente com RNF-10 da visão geral. |
| RF-RANK-04 | Registrar os scores de re-ranking de cada chunk (rastreabilidade — RF-10 da visão geral). |
| RF-RANK-05 | O `Reranker` deve ser uma porta substituível (RNF-06 da arquitetura), permitindo trocar o modelo/método sem impacto em `Retriever` ou `ContextBuilder`. |

---

## 4. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-RANK-01 | O re-ranking deve considerar a contenção de GPU já existente (LM Studio + embeddings, `arquitetura.md`) — priorizar modelos de re-ranking leves (cross-encoders pequenos) ou re-ranking baseado em CPU, se a qualidade for aceitável. |
| RNF-RANK-02 | Latência adicional do re-ranking deve ser compatível com uso interativo — medir e comparar contra o ganho de qualidade obtido. |
| RNF-RANK-03 | A decisão de usar (ou não) re-ranking, e qual modelo usar, deve ser validada por benchmark (Precision@K, Recall@K, MRR, nDCG antes/depois do re-ranking), não assumida como benéfica por padrão. |

---

## 5. Candidatos de Re-ranking

| Abordagem | Notas |
|-----------|-------|
| **Cross-encoder multilíngue leve** (ex.: variantes pequenas de `bge-reranker`, `jina-reranker`, ou `ms-marco-MiniLM` multilíngue) | Boa precisão de re-ranking; footprint de VRAM/CPU a validar dado o compartilhamento de GPU já existente. Preferir variantes "small"/"base" para minimizar contenção. |
| **Re-ranking via LLM local (LM Studio)** | Usar o próprio `qwen/qwen3.5-9b` para pontuar relevância de cada chunk via prompt | Mais preciso potencialmente, mas caro computacionalmente (uma chamada de LLM por chunk candidato) e compete diretamente pelo mesmo recurso que a geração da resposta final — risco de latência alta |
| **Sem re-ranking (apenas busca vetorial)** | Baseline mínimo | Serve como ponto de comparação no benchmark; não é a expectativa final, dado que a spec de recuperação já é otimizada para recall, não necessariamente para precisão fina |

**Recomendação inicial (a validar por benchmark):** cross-encoder multilíngue leve, rodando em CPU se a latência for aceitável, evitando competir com a GPU já compartilhada entre LM Studio e embeddings.

---

## 6. Dependências

* `Retriever` retornando top-N candidatos (`recuperacao.md`).
* Golden set de perguntas de referência (`testes.md`) para medir ganho de qualidade do re-ranking.
* Modelo de cross-encoder a escolher — decisão técnica final registrada em ADR após benchmark.

---

## 7. Critérios de Aceitação

* [ ] Re-ranking reordena corretamente os candidatos, validado com casos de teste onde a ordem esperada é conhecida.
* [ ] Ganho (ou ausência de ganho) de métricas de qualidade (Precision@K, Recall@K, MRR, nDCG) com re-ranking está documentado e comparado ao baseline sem re-ranking.
* [ ] Latência adicional do re-ranking é medida e considerada aceitável para uso interativo.
* [ ] Scores de re-ranking são registrados para rastreabilidade.

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Re-ranking via LLM local competiria pela mesma GPU usada na resposta final, gerando latência inaceitável | Alto | Priorizar cross-encoder leve e dedicado em vez de reusar a LLM principal para essa tarefa |
| Cross-encoder pode não ter suporte robusto para português especificamente | Médio | Validar qualidade no golden set interno, não apenas em benchmarks públicos genéricos |
| Adicionar re-ranking pode não compensar a latência extra se o ganho de qualidade for marginal | Médio | Processo de benchmark obrigatório (RNF-RANK-03) antes de decidir manter o re-ranking em produção |

---

## 9. Alternativas Avaliadas

Ver seção 5 — a decisão final entre as abordagens será tomada com base em benchmark real (qualidade vs. latência vs. uso de recursos), documentada em ADR.

---

## 10. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Priorizar cross-encoder leve (CPU, se viável) em vez de re-ranking via LLM local | Evita contenção adicional na GPU já compartilhada (`arquitetura.md`) | Proposto |
| Decisão de manter ou não o re-ranking em produção depende de benchmark de custo-benefício | Alinhado à diretriz do projeto de nunca assumir ganhos sem medição | Proposto |

---

## 11. Estratégia de Testes

* **Unitários:** lógica de reordenação e corte para top-K, testada isoladamente.
* **Integração:** recuperação → re-ranking → saída ordenada, validando o fluxo completo.
* **Benchmark (crítico):** comparação de métricas de qualidade com/sem re-ranking, e entre diferentes modelos de cross-encoder candidatos, no golden set.
* **Desempenho:** latência adicional medida e reportada.

---

## 12. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado e aprovado na mesma revisão (v1.0) | Nenhuma pendência bloqueante; escolha final do cross-encoder condicionada a benchmark durante implementação |

---

**Próximo passo:** avançar para `construcao-contexto.md` — a etapa mais crítica do projeto, conforme `visao-geral.md`.
