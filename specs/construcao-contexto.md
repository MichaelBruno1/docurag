# Especificação: Construção do Contexto

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `reranking.md` (v1.0), `chunking.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Esta é **a etapa mais importante do projeto**, conforme `visao-geral.md`. Montar o contexto final enviado à LLM (`qwen/qwen3.5-9b`, contexto de 8k tokens confirmado) a partir dos chunks re-ranqueados, garantindo: apenas informação relevante, eliminação de redundância, remoção de ruído, respeito ao limite de tokens, organização lógica, e preservação de contexto suficiente para uma resposta correta.

---

## 2. Escopo

Cobre a implementação do `ContextBuilder` (porta definida em `arquitetura.md`), que recebe os chunks re-ranqueados (`reranking.md`) e produz o texto final de contexto + prompt estruturado a ser enviado ao `LLMProvider` (`llm.md`). Não cobre a chamada à LLM em si (`llm.md`).

---

## 3. Orçamento de Tokens (Base de Cálculo)

Conforme já antecipado em `chunking.md`, o contexto total do `qwen/qwen3.5-9b` é de **8.000 tokens**. Este orçamento deve ser dividido entre:

| Componente | Estimativa de tokens | Observação |
|------------|------------------------|------------|
| Prompt de sistema (instruções, persona, formato de resposta) | ~200-400 | Definido em `llm.md`; deve ser mantido enxuto |
| Pergunta do usuário | ~50-200 | Variável, tipicamente curta |
| **Chunks recuperados (contexto)** | **~4.500-5.500** | Orçamento principal desta spec |
| Margem de segurança + tokens de formatação/estrutura | ~300-500 | Buffer para evitar estouro de contexto |
| Espaço reservado para a resposta gerada | ~1.500-2.500 | A LLM precisa de espaço para gerar a resposta dentro da janela total de 8k |

**Este é o orçamento crítico que toda a estratégia de construção de contexto deve respeitar rigorosamente — estourar o limite de 8k tokens é uma falha grave, não apenas uma questão de qualidade.**

---

## 4. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-CTX-01 | Selecionar, entre os chunks re-ranqueados, o subconjunto que cabe no orçamento de tokens (seção 3), priorizando os de maior score de re-ranking. |
| RF-CTX-02 | Eliminar redundância entre chunks selecionados (ex.: dois chunks com alta sobreposição de conteúdo) antes de incluir ambos, mesmo que os dois tenham score alto — preferir diversidade de informação dentro do orçamento. |
| RF-CTX-03 | **Confirmado:** organizar os chunks selecionados por **ordem de relevância decrescente** (score de re-ranking), não pela ordem estrutural original do documento. |
| RF-CTX-04 | Incluir, junto a cada chunk no contexto, uma referência mínima de origem (ex.: nome do documento/seção) que permita à LLM citar a fonte na resposta, sem incluir metadados excessivos que consumam tokens desnecessariamente. |
| RF-CTX-05 | Truncar ou excluir chunks de baixa confiança de OCR (marcados em `enriquecimento.md`/`normalizacao.md`) quando o orçamento de tokens for escasso, priorizando chunks de alta confiança. |
| RF-CTX-06 | Contar tokens usando o tokenizer real do `qwen/qwen3.5-9b` (não uma aproximação genérica), para respeitar o orçamento com precisão. |
| RF-CTX-07 | Registrar, para cada resposta gerada, exatamente quais chunks foram incluídos no contexto final (para rastreabilidade completa — RF-10 da visão geral) e quais foram descartados por causa do orçamento. |

---

## 5. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-CTX-01 | **Nunca exceder o limite de tokens do modelo** (8k) — este é o requisito não funcional mais crítico desta spec; qualquer violação é considerada falha grave. |
| RNF-CTX-02 | Minimizar tokens desperdiçados com informação irrelevante ou redundante (RNF-02, RNF-03 da visão geral). |
| RNF-CTX-03 | A estrutura do contexto deve ser facilmente interpretável por um modelo de 4B–9B parâmetros — evitar formatos excessivamente aninhados ou verbosos; preferir clareza direta (RNF-04 da visão geral). |
| RNF-CTX-04 | O processo de seleção/organização deve ser determinístico dado o mesmo conjunto de chunks re-ranqueados de entrada (facilita testes e debugging). |

---

## 6. Estratégia de Construção (Proposta)

1. Receber lista de chunks re-ranqueados (ordenados por score decrescente).
2. Calcular tokens disponíveis para chunks: `8000 - prompt_sistema - pergunta_usuario - margem_seguranca - espaço_resposta` (conforme seção 3), usando o tokenizer real do modelo.
3. Iterar pelos chunks em ordem de score, incluindo cada um se: (a) ainda houver orçamento de tokens, e (b) não for redundante o suficiente com um chunk já incluído (medido por similaridade de conteúdo/embedding acima de um threshold).
4. Parar quando o orçamento se esgotar ou os candidatos se esgotarem.
5. Organizar os chunks incluídos por **ordem de relevância decrescente** (confirmado pelo usuário) — o chunk de maior score de re-ranking aparece primeiro no prompt.
6. Anexar referência mínima de origem a cada chunk (RF-CTX-04).
7. Montar o prompt final, validar contagem total de tokens antes de enviar (double-check de segurança contra RNF-CTX-01).

---

## 7. Dependências

* Chunks re-ranqueados (`reranking.md`).
* Tokenizer do `qwen/qwen3.5-9b` (via LM Studio ou biblioteca compatível, ex. `tiktoken`-equivalente para modelos Qwen) — necessário para contagem precisa de tokens (RF-CTX-06).
* Estrutura de prompt de sistema definida em `llm.md` (dependência circular leve: esta spec assume um orçamento para o prompt de sistema, que será finalizado em `llm.md`; ambos devem ser co-desenvolvidos/ajustados iterativamente).
* Golden set (`testes.md`) para validar diferentes estratégias de organização/seleção via benchmark.

---

## 8. Critérios de Aceitação

* [ ] O contexto final nunca excede o limite de tokens do modelo (validado com contagem real via tokenizer, não estimativa).
* [ ] Chunks redundantes entre si não são incluídos simultaneamente quando isso desperdiça orçamento sem ganho de informação.
* [ ] Cada chunk incluído carrega referência de origem suficiente para citação.
* [ ] Chunks de baixa confiança de OCR são despriorizados quando o orçamento é escasso.
* [ ] O processo é determinístico e testável.
* [ ] Rastreabilidade completa: quais chunks entraram no contexto final e quais foram descartados, e por quê.
* [ ] Diferentes estratégias de organização (ordem de score vs. ordem estrutural) foram comparadas via benchmark de qualidade de resposta.

---

## 9. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Estourar o limite de 8k tokens causa erro ou truncamento abrupto pela LLM | Crítico | Contagem real de tokens antes do envio (RF-CTX-06) + margem de segurança explícita (seção 3) |
| Orçamento de ~4.500-5.500 tokens para chunks pode ser insuficiente se o tamanho de chunk escolhido em `chunking.md` for grande demais | Alto | Coordenar diretamente com o benchmark de tamanho de chunk (`chunking.md`, seção 6) — o orçamento aqui e o tamanho de chunk lá devem ser calibrados em conjunto |
| Deduplicação por similaridade pode remover chunks complementares por engano | Médio | Calibrar threshold de similaridade cuidadosamente, validado no golden set |
| Ordem de apresentação dos chunks pode afetar a qualidade da resposta de forma não intuitiva (LLMs pequenas podem ser mais sensíveis a posição no contexto — fenômeno conhecido como "lost in the middle", onde conteúdo no meio do contexto recebe menos atenção que início/fim) | Médio (mitigado) | **Confirmado: ordem por relevância decrescente** — o chunk mais relevante fica no início do contexto, favorecido pelo efeito de primazia; chunks de menor relevância (mais suscetíveis a serem "perdidos") já são os menos críticos para a resposta |

---

## 10. Alternativas Avaliadas

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| Incluir o máximo de chunks possível até o limite de tokens (sem dedup) | Simples | Desperdiça orçamento com redundância, reduz diversidade de informação | Rejeitado |
| Seleção gulosa (greedy) por score + deduplicação por similaridade | Equilíbrio entre relevância e diversidade, implementação relativamente simples | Não é ótimo global (poderia haver combinação melhor de chunks) | **Proposto para v1** — ótimo global (ex.: programação dinâmica tipo "knapsack") é over-engineering para o ganho marginal esperado |
| Sumarização de chunks via LLM antes de incluir no contexto (para caber mais informação) | Poderia incluir mais fontes no mesmo orçamento | Custo computacional adicional (chamada de LLM extra), risco de perda/alteração de informação factual, contraria RNF-04 (facilidade de interpretação por modelo pequeno se a sumarização for malfeita) | Rejeitado para v1 — risco de introduzir alucinação antes mesmo da resposta final |

---

## 11. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Orçamento de ~4.500-5.500 tokens para chunks, dentro do limite de 8k do modelo | Calibrado à realidade confirmada do `qwen/qwen3.5-9b` (`chunking.md`, `embeddings.md`) | Proposto |
| Seleção gulosa por score + deduplicação por similaridade (sem sumarização via LLM) | Equilíbrio entre qualidade, simplicidade e ausência de risco de alucinação intermediária | Proposto |
| Contagem de tokens via tokenizer real do modelo, não estimativa | Requisito crítico (RNF-CTX-01) — nunca estourar o contexto | Proposto |

---

## 12. Estratégia de Testes

* **Unitários:** cálculo de orçamento de tokens, deduplicação, corte por limite, testados isoladamente com casos-limite (chunks que somados excedem exatamente o limite).
* **Integração:** re-ranking → construção de contexto → prompt final, validando que o prompt nunca excede 8k tokens.
* **Benchmark (crítico):** comparação de estratégias de organização (ordem de score vs. estrutural) e de threshold de deduplicação, medindo qualidade final da resposta da LLM no golden set — esta é a validação mais importante de todo o projeto, conforme `visao-geral.md`.
* **Regressão:** mesmo conjunto de chunks de entrada deve gerar o mesmo contexto final (determinismo).

---

## 13. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Decisões confirmadas pelo usuário | Ordem por relevância decrescente confirmada; orçamento de ~4.500-5.500 tokens para chunks mantido como planejado |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `llm.md` |

---

**Próximo passo:** avançar para `llm.md`, detalhando a integração com o LM Studio e o design do prompt de sistema.
