# Especificação: Embeddings

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `chunking.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Selecionar, via comparação técnica e benchmark reproduzível, o modelo de embedding que será usado tanto para (a) indexação vetorial dos chunks quanto para (b) detecção de fronteiras semânticas no chunking (`chunking.md`, seção 3.2), otimizando para qualidade semântica em português, execução local eficiente e coexistência com o LM Studio na GPU compartilhada.

---

## 2. Escopo

Cobre a avaliação comparativa de modelos de embedding candidatos e a definição do processo de benchmark que levará à escolha final (registrada em ADR próprio). Não cobre a implementação do banco vetorial (`banco-vetorial.md`) nem a lógica de busca (`recuperacao.md`).

---

## 3. Critérios de Avaliação

Conforme `visao-geral.md`, a escolha deve ser baseada em benchmarks reproduzíveis, avaliando:

| Critério | Como será medido |
|----------|-------------------|
| Qualidade semântica | Scores em benchmarks públicos (MTEB Multilingual/Retrieval) como referência inicial, **validados com o golden set interno** (`testes.md`) como critério decisivo |
| Desempenho em português | Desempenho específico em tarefas de retrieval/STS em português (quando disponível em benchmarks públicos), complementado pelo golden set interno |
| Velocidade | Tempo médio de geração de embedding por chunk, medido localmente na infraestrutura real |
| Consumo de memória/VRAM | Footprint do modelo carregado, crítico dado o compartilhamento de GPU com o LM Studio (`arquitetura.md`) |
| Compatibilidade com execução local | Licença permissiva para uso interno, disponibilidade via `sentence-transformers`/Hugging Face, sem dependência de API externa |

---

## 4. Orçamento de VRAM Confirmado

**GPU disponível:** 16GB de VRAM (confirmado pelo usuário), compartilhada entre LM Studio e o serviço de embeddings.

**LLM confirmado:** `qwen/qwen3.5-9b`. Pesquisa técnica indica consumo de aproximadamente 5,5GB em quantização Q4_K_M e cerca de 9,6GB em Q8_0 — a quantização exata a ser usada no LM Studio impacta diretamente o orçamento restante:

| Cenário de quantização da LLM | VRAM da LLM | VRAM restante para embeddings + KV cache/contexto |
|-------------------------------|-------------|------------------------------------------------------|
| Q4_K_M (mais leve, leve perda de qualidade) | ~5,5GB | ~10,5GB disponíveis |
| Q6_K (equilíbrio) | ~7-7,5GB | ~8,5-9GB disponíveis |
| Q8_0 (quase sem perda de qualidade) | ~9,6GB | ~6,4GB disponíveis |

**Implicação prática:** mesmo no cenário mais conservador (Q8_0), sobram ~6,4GB de VRAM — orçamento confortável para qualquer um dos candidatos leves/médios da seção 5 (BGE-M3, família E5), inclusive com margem para KV cache de contexto (8k tokens, conforme `chunking.md`) e picos de uso simultâneo durante o chunking semântico. Modelos muito grandes de embedding (ex.: variantes 8B da família Qwen3-Embedding) devem ser evitados ou testados com cautela adicional.

**Recomendação para o benchmark:** priorizar a quantização da LLM que a equipe já pretende usar operacionalmente (qualidade de resposta é prioridade, dado RNF-01 da visão geral sobre precisão), e calibrar o benchmark de embeddings em torno da VRAM restante real desse cenário escolhido. **Dado o orçamento confortável identificado, recomenda-se iniciar o benchmark pelos candidatos BGE-M3 e multilingual-e5-large, que oferecem melhor qualidade semântica sem risco relevante de contenção de VRAM neste cenário.**

---

## 5. Candidatos para Benchmark

Levantamento inicial de modelos open-source com bom desempenho multilíngue/português e viáveis para execução local em 2026, para servirem de ponto de partida do benchmark (a lista não é exaustiva nem definitiva — novos candidatos podem ser adicionados):

| Modelo | Dimensões | Notas relevantes |
|--------|-----------|-------------------|
| `BAAI/bge-m3` | 1024 | Modelo multilíngue com suporte multilíngue e qualidade de estado da arte amplamente adotado; bom equilíbrio entre qualidade e footprint. Licença permissiva (MIT), sem restrição de uso comercial/interno. |
| `intfloat/multilingual-e5-base` / `multilingual-e5-small` | 768 / 384 | Suporta mais de 100 idiomas incluindo português, roda localmente sem necessidade de chave de API; a versão *small* é leve, adequada como candidato "seguro" de baixo custo computacional. |
| `intfloat/multilingual-e5-large` | 1024 | Versão maior da família e5, melhor qualidade semântica ao custo de mais VRAM/latência — viável dado o orçamento de ~6,4-10,5GB calculado na seção 4. |
| Jina Embeddings (v5 small / v3) | 1024 | Modelo de alta colocação em leaderboards de retrieval multilíngue, competitivo mesmo frente a modelos maiores — **atenção**: algumas versões usam licença CC BY-NC, que pode restringir uso comercial direto; validar se aplicável ao uso corporativo interno antes de adotar. |
| Qwen3-Embedding (variantes menores, ex. 0.6B/4B) | variável | Família recente com alto nDCG@10 e embeddings de alta dimensionalidade; variantes maiores (8B) desaconselhadas mesmo com o orçamento de VRAM disponível, para preservar margem de segurança — considerar apenas versões menores. |

**Fora de escopo como candidatos principais:** modelos proprietários via API (OpenAI, Voyage, Cohere) — contrariam o requisito de execução 100% dentro da cloud privada (RNF-10 da `visao-geral.md`), a menos que uma exceção seja explicitamente aprovada.

---

## 6. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-EMB-01 | Gerar embeddings para chunks (indexação) e para sentenças/parágrafos (detecção de fronteira no chunking) usando o **mesmo modelo**, evitando duas dependências de modelo distintas. |
| RF-EMB-02 | Suportar geração em lote (batch) para eficiência durante a indexação de múltiplos documentos. |
| RF-EMB-03 | Expor o `EmbeddingProvider` como porta plugável (conforme `arquitetura.md`), permitindo trocar o modelo sem alterar `Retriever`, `ContextBuilder` ou `Chunker`. |
| RF-EMB-04 | Versionar o modelo de embedding utilizado nos metadados do índice, para permitir reindexação completa caso o modelo seja trocado no futuro (embeddings de modelos diferentes não são comparáveis entre si). |

---

## 7. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-EMB-01 | O modelo escolhido deve operar com footprint de VRAM compatível com a coexistência simultânea com o LM Studio na mesma GPU (`arquitetura.md`, seção 6), respeitando o orçamento calculado na seção 4. |
| RNF-EMB-02 | Latência de geração de embedding não deve se tornar o gargalo do pipeline de indexação nem da consulta em tempo real. |
| RNF-EMB-03 | Licença do modelo deve permitir uso interno corporativo sem restrições problemáticas (atenção especial a modelos com licença CC BY-NC). |

---

## 8. Dependências

* `chunking.md` (v1.0) — define o duplo uso do modelo de embedding (indexação + detecção de fronteira semântica).
* GPU confirmada: 16GB VRAM, LLM `qwen/qwen3.5-9b` (ver seção 4).
* Golden set de perguntas de referência (`testes.md`) para validação de qualidade específica ao domínio/idioma do corpus — a ser construído em conjunto, conforme já indicado em `chunking.md`.

---

## 9. Processo de Benchmark (a executar antes da decisão final)

1. Carregar o LM Studio com `qwen/qwen3.5-9b` na quantização escolhida para operação (ver seção 4), simulando uso real de VRAM.
2. Para cada modelo candidato (seção 5): carregar simultaneamente e medir VRAM residual disponível, tempo médio de embedding por chunk (amostra do corpus real), e verificar se há erros de falta de memória.
3. Gerar embeddings para o golden set e chunks de teste; medir Precision@K/Recall@K/MRR/nDCG na recuperação resultante.
4. Descartar candidatos que não coexistam de forma estável com o LM Studio na GPU compartilhada (não esperado, dado o orçamento confortável calculado, mas deve ser validado empiricamente).
5. Entre os candidatos estáveis, selecionar o de melhor qualidade de recuperação no golden set.
6. Documentar resultado em ADR (`ADR-00X-modelo-embedding.md`).

---

## 10. Critérios de Aceitação

* [ ] Pelo menos 3 modelos candidatos foram testados sob coexistência real com o LM Studio na GPU.
* [ ] Métricas de VRAM, latência e qualidade (Precision@K, Recall@K, MRR, nDCG) foram registradas para cada candidato testado.
* [ ] O modelo final escolhido não causa falhas de memória quando o LM Studio está ativo simultaneamente.
* [ ] A decisão final está documentada em ADR com evidências do benchmark.
* [ ] O mesmo modelo é usado tanto para indexação quanto para chunking semântico (RF-EMB-01).

---

## 11. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Contenção de VRAM entre LM Studio e modelo de embedding | Baixo (mitigado) | Orçamento de ~6,4-10,5GB calculado na seção 4 é confortável para os candidatos propostos; validar empiricamente mesmo assim |
| Benchmarks públicos (MTEB) não refletem necessariamente o desempenho no domínio técnico/corporativo específico | Médio | Golden set interno é o critério decisivo, não apenas os scores públicos |
| Licenças restritivas (ex.: CC BY-NC de algumas variantes Jina) podem inviabilizar uso mesmo sendo tecnicamente superiores | Médio | Verificar explicitamente a licença de cada candidato antes do benchmark, descartando os incompatíveis com uso corporativo interno |
| Modelo escolhido pode precisar ser trocado no futuro, exigindo reindexação completa | Baixo (corpus pequeno) | Versionamento do modelo nos metadados (RF-EMB-04) simplifica reindexação quando necessário |

---

## 12. Alternativas Avaliadas

*A comparação técnica completa (com métricas reais medidas na infraestrutura do usuário) será registrada como parte do resultado do benchmark, não nesta spec. Ver seção 5 para o levantamento inicial de candidatos.*

---

## 13. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Um único modelo de embedding para indexação e chunking semântico | Simplicidade operacional; evita duas dependências de modelo (RF-EMB-01) | Proposto |
| Critério de corte por VRAM compatível com LM Studio (orçamento calculado na seção 4) | Reflete a realidade de infraestrutura confirmada (16GB VRAM, GPU compartilhada com `qwen/qwen3.5-9b`) | ✅ Confirmado |
| Modelos proprietários via API excluídos como candidatos principais | Alinhado ao requisito de execução em cloud privada (RNF-10 da visão geral) | Proposto |
| Priorizar BGE-M3 e multilingual-e5-large como primeiros candidatos do benchmark | Melhor qualidade semântica esperada, viável dado o orçamento de VRAM confortável | Proposto |

---

## 14. Estratégia de Testes

* **Benchmark de coexistência de GPU:** conforme seção 9.
* **Benchmark de qualidade:** golden set interno, métricas de retrieval.
* **Testes de contrato:** `EmbeddingProvider` deve respeitar a interface definida em `arquitetura.md`, independentemente do modelo escolhido.
* **Regressão:** garantir que trocar o modelo (mudança de configuração) não quebra o pipeline, apenas exige reindexação.

---

## 15. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Decisões confirmadas pelo usuário | GPU: 16GB VRAM; LLM: `qwen/qwen3.5-9b`. Pesquisa técnica confirmou orçamento de VRAM confortável (~6,4-10,5GB restantes conforme quantização da LLM) |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `banco-vetorial.md` |

**⚠️ Nota para revisão futura:** a quantização exata do `qwen/qwen3.5-9b` a ser usada em produção (Q4_K_M, Q6_K ou Q8_0) ainda não foi definida — deve ser decidida com base em testes de qualidade de resposta (não é objeto desta spec) e comunicada para calibrar o benchmark de embeddings da seção 9.

---

**Próximo passo:** avançar para `banco-vetorial.md`, comparando tecnicamente Qdrant, ChromaDB, FAISS, Milvus e pgvector.
