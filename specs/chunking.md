# Especificação: Chunking (Estratégia de Divisão em Chunks)

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `enriquecimento.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Dividir o documento normalizado e enriquecido em unidades (chunks) que preservem significado semântico completo, otimizadas para recuperação precisa e para consumo por LLMs de 4B–9B parâmetros. Esta é uma das etapas mais determinantes para a qualidade final do RAG (junto com `construcao-contexto.md`).

---

## 2. Escopo

Cobre a estratégia de divisão em chunks, geração do `chunk_id`, e finalização dos metadados de relacionamento entre chunks (chunk anterior/próximo, chunk-pai de seção) mencionados em `enriquecimento.md`. Não cobre geração de embeddings (`embeddings.md`) nem indexação (`indexacao.md`).

---

## 3. Estratégia de Chunking

Conforme diretriz do projeto, **chunk fixo (tamanho arbitrário) é evitado** quando causa perda de significado. A estratégia proposta é híbrida, priorizada nesta ordem:

### 3.1 Chunking por Seção (base estrutural)
Usar a hierarquia de seções extraída em `parsing.md`/`enriquecimento.md` (capítulo → seção → subtítulo) como unidade primária de divisão. Uma seção coesa e de tamanho razoável se torna um chunk.

### 3.2 Chunking Semântico (refinamento dentro de seções grandes) — Confirmado para v1

**Confirmado pelo usuário: implementado desde a v1.** Quando uma seção excede o tamanho-alvo de chunk (a definir por experimentação, ver seção 4), dividir por limites semânticos usando **similaridade de embeddings entre sentenças/parágrafos adjacentes** para detectar pontos de quebra naturais (ex.: calcular embedding de cada sentença/parágrafo, medir queda de similaridade coseno entre vizinhos, e cortar nos pontos de menor similaridade — técnica de "semantic splitting").

### 3.3 Chunking Hierárquico (preservação de contexto pai)
Cada chunk carrega referência ao seu "chunk-pai" (a seção/capítulo ao qual pertence), permitindo, quando necessário, recuperar contexto adicional (ex.: resumo da seção-pai) sem incluir todo o texto no chunk-filho.

### 3.4 Chunking Adaptativo (ajuste por tipo de conteúdo)
Conteúdo tabular (XLSX, tabelas em DOCX/PDF) não deve ser dividido por contagem de tokens da mesma forma que texto corrido — tabelas devem ser mantidas íntegras sempre que couberem no limite de chunk, ou divididas por linhas/blocos lógicos preservando cabeçalho em cada divisão.

**Chunk fixo por tamanho** é usado apenas como fallback de segurança, quando nenhuma quebra semântica/estrutural razoável é encontrada dentro de um limite máximo de tamanho.

---

## 4. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-CHUNK-01 | Dividir documentos primariamente por seção estrutural (título/subtítulo), não por contagem fixa de caracteres. |
| RF-CHUNK-02 | Subdividir seções grandes por limites semânticos (parágrafo/sentença), evitando cortar no meio de uma ideia. |
| RF-CHUNK-03 | Preservar tabelas íntegras dentro de um chunk sempre que couberem no limite de tamanho; caso não caibam, dividir preservando cabeçalho em cada parte. |
| RF-CHUNK-04 | Gerar `chunk_id` único e determinístico (mesmo documento processado novamente gera os mesmos IDs, permitindo upsert idempotente — alinhado a RF-ING-07 de `ingestao.md`). |
| RF-CHUNK-05 | Registrar relacionamento entre chunks: chunk anterior, chunk seguinte, e chunk-pai de seção (referência à seção/capítulo). |
| RF-CHUNK-06 | Propagar todos os metadados gerados em `enriquecimento.md` para cada chunk resultante. |
| RF-CHUNK-07 | O tamanho-alvo de chunk (em tokens) deve ser definido por **experimentação via benchmark**, não por conveniência arbitrária (conforme diretriz do projeto) — ver seção 6. |
| RF-CHUNK-08 | Aplicar um limite máximo rígido de tamanho por chunk (fallback de segurança), calibrado ao **contexto de 8k tokens confirmado** do(s) modelo(s) LLM 4B–9B no LM Studio — nenhum chunk individual deve se aproximar desse teto (ver orçamento detalhado na seção 6). |

---

## 5. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-CHUNK-01 | O processo de chunking deve ser determinístico (RF-CHUNK-04) para permitir reingestão/upsert sem duplicação. |
| RNF-CHUNK-02 | A estratégia deve ser configurável (tamanho-alvo, estratégia de quebra semântica) sem exigir alteração de código — parâmetros ajustáveis via configuração para facilitar experimentação de benchmark. |
| RNF-CHUNK-03 | **Confirmado:** chunking semântico (3.2) usa embeddings para detectar pontos de quebra desde a v1. Isso introduz uso adicional do serviço de embeddings (já compartilhando GPU com LM Studio — `arquitetura.md`); deve ser medido o impacto de desempenho/contenção via benchmark, e considerar cache de embeddings intermediários de sentença para evitar recomputo em `embeddings.md` (chunk final vs. embedding usado só para detecção de fronteira). |

---

## 6. Definição de Tamanho de Chunk — Processo Experimental

Conforme diretriz do projeto ("o tamanho do chunk deve ser definido por experimentação e métricas, não por conveniência"), este documento **não fixa um valor definitivo agora**, mas já incorpora a restrição confirmada: **o(s) modelo(s) LLM no LM Studio têm contexto de 8k tokens.**

Essa restrição é significativa: com 8k tokens de contexto total, é preciso reservar espaço para o prompt de sistema, a pergunta do usuário, e a resposta gerada — sobrando um orçamento realista de aproximadamente **4k–5k tokens para os chunks recuperados** (valor a ser refinado quando `llm.md`/`construcao-contexto.md` definirem o prompt exato). Isso torna a escolha do tamanho de chunk ainda mais crítica: chunks grandes demais permitem incluir poucos chunks no contexto (baixa diversidade de fontes); chunks pequenos demais podem fragmentar demais o significado.

1. Gerar candidatos de tamanho-alvo **calibrados ao orçamento de ~4k–5k tokens de contexto**: por exemplo, 128, 256, 512 tokens (evitando candidatos como 1024+ que, com K=5 chunks recuperados, já consumiriam sozinhos todo o orçamento disponível).
2. Executar o golden set de perguntas de referência (a construir em conjunto com `testes.md`/`benchmark.md` — ver seção 7) contra cada configuração.
3. Medir Precision@K, Recall@K, MRR, nDCG, e também métricas de contexto (tokens médios enviados, redundância) para cada tamanho.
4. Selecionar o tamanho que maximiza qualidade de recuperação **e** minimiza tokens desperdiçados, respeitando o teto rígido de ~8k tokens de contexto total do modelo.
5. Documentar a escolha final em ADR próprio (`ADR-00X-tamanho-chunk.md`), com os resultados do benchmark como evidência.

---

## 7. Dependências

* `ParsedDocument` enriquecido (saída de `enriquecimento.md`).
* **Golden set de perguntas de referência**: confirmado que será construído **em conjunto** com esta spec e com `testes.md`/`benchmark.md` — não existe ainda. Recomenda-se criar uma primeira versão pequena (ex.: 15–30 perguntas) com base em uma amostra representativa do corpus real, antes de rodar o processo experimental da seção 6, expandindo-o iterativamente conforme `testes.md` for detalhado.
* Modelo de embedding para chunking semântico (confirmado como necessário na v1, seção 3.2) — depende de decisão em `embeddings.md`. **Dependência circular explícita:** chunking semântico precisa de um modelo de embedding para detectar fronteiras, mas a escolha definitiva do modelo de embedding (`embeddings.md`) normalmente viria depois. Resolução proposta: usar o mesmo modelo de embedding que será escolhido para indexação (evitando duas dependências de modelo diferentes), aceitando que `chunking.md` e `embeddings.md` sejam desenvolvidos com alguma iteração conjunta.

---

## 8. Critérios de Aceitação

* [ ] Documentos são divididos respeitando a hierarquia de seções antes de qualquer corte por tamanho.
* [ ] Tabelas não são cortadas no meio sem preservar cabeçalho.
* [ ] `chunk_id` é determinístico: reprocessar o mesmo documento gera os mesmos IDs.
* [ ] Cada chunk carrega metadados completos herdados de `enriquecimento.md`, mais `chunk_id`, chunk anterior/próximo, e chunk-pai.
* [ ] Processo de benchmark de tamanho de chunk (seção 6) está implementado e produz um relatório comparativo.
* [ ] Nenhum chunk excede o limite máximo rígido definido (RF-CHUNK-08).

---

## 9. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Chunking semântico via embeddings adiciona custo computacional e complexidade | Médio | Avaliar via benchmark se o ganho de qualidade justifica o custo; ter fallback mais simples (quebra por parágrafo) caso não justifique |
| Seções muito desbalanceadas (uma seção enorme, outra minúscula) podem gerar chunks de qualidade desigual | Médio | Chunking adaptativo (3.4) e subdivisão semântica (3.2) mitigam isso |
| Dependência circular entre golden set (para benchmark) e corpus real | Baixo-Médio | Criar golden set inicial com amostra representativa antes de finalizar tamanho de chunk; revisar iterativamente |
| Tamanho de chunk mal calibrado prejudica desproporcionalmente modelos pequenos (4B–9B) | Alto | Processo experimental obrigatório (seção 6) antes de finalizar; nunca usar valor "de conveniência" |

---

## 10. Alternativas Avaliadas

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| Chunk fixo por tamanho (ex.: sempre 512 tokens) | Simples de implementar | Corta no meio de ideias, perde significado, diretriz do projeto explicitamente desaconselha | Rejeitado como estratégia primária (mantido apenas como fallback de segurança) |
| Chunking por seção + refinamento semântico via embeddings + hierárquico + adaptativo (híbrido completo) | Preserva significado, adequado a modelos pequenos com contexto limitado (8k), alinhado às diretrizes do projeto | Mais complexo de implementar e testar; introduz uso adicional do serviço de embeddings | **✅ Confirmado para v1** |
| Híbrido sem refinamento semântico (apenas seção + parágrafo) | Mais simples, sem custo adicional de embeddings | Qualidade de quebra inferior em seções muito longas | Rejeitado — usuário confirmou que quer semântico já na v1 |

---

## 11. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Estratégia híbrida (seção + semântico + hierárquico + adaptativo), com chunk fixo apenas como fallback | Alinhado às diretrizes explícitas do projeto e ao objetivo de otimizar para LLMs pequenas | Proposto |
| Tamanho de chunk definido por benchmark, não fixado nesta spec | Diretriz explícita do projeto ("nunca por conveniência") | Proposto |
| `chunk_id` determinístico (hash de conteúdo + posição, não UUID aleatório) | Permite upsert idempotente sem duplicação | Proposto |

---

## 12. Estratégia de Testes

* **Unitários:** cada regra de chunking (por seção, semântico, tabular) testada isoladamente com documentos de exemplo.
* **Integração:** enriquecimento → chunking, validando propagação de metadados e geração de relacionamentos.
* **Regressão:** reprocessar o mesmo documento deve gerar os mesmos `chunk_id`s.
* **Benchmark (crítico):** comparação sistemática de tamanhos/estratégias de chunk via golden set, conforme processo da seção 6 — este é o teste mais importante desta spec.

---

## 13. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Decisões confirmadas pelo usuário | Chunking semântico via embeddings confirmado na v1; golden set será construído junto com `testes.md`/`benchmark.md`; contexto do LLM confirmado em 8k tokens |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `embeddings.md` |

**⚠️ Notas importantes para as próximas specs:**
* `embeddings.md` deve considerar que o modelo escolhido será usado tanto para indexação quanto para detecção de fronteiras semânticas no chunking — uma única escolha de modelo serve a ambos os propósitos.
* `construcao-contexto.md` deve trabalhar com um orçamento realista de **~4k–5k tokens para chunks recuperados**, dado o contexto total de 8k do LLM e a necessidade de espaço para prompt de sistema, pergunta e resposta.
* O golden set inicial (mesmo pequeno) precisa existir antes de rodar o benchmark de tamanho de chunk da seção 6 — coordenar com `testes.md`.

---

**Próximo passo:** avançar para `embeddings.md`, comparando tecnicamente modelos de embedding para português e execução local, já considerando o duplo uso (indexação + chunking semântico) e a coexistência de GPU com o LM Studio.
