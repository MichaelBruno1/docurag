# Especificação: Banco Vetorial

**Status:** ✅ Aprovado (com premissa assumida — ver seção 13)
**Versão:** 1.0
**Depende de:** `arquitetura.md` (v1.0), `embeddings.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Selecionar, via comparação técnica, o banco vetorial que armazenará os embeddings dos chunks e permitirá busca por similaridade combinada com filtros de metadados, respeitando as restrições já confirmadas: corpus pequeno (<1.000 documentos), monólito modular, ausência de orquestrador de containers, e ausência de multi-tenancy.

---

## 2. Escopo

Cobre a comparação técnica e a decisão sobre a porta `VectorStore` (definida em `arquitetura.md`). Não cobre a lógica de busca híbrida/re-ranking (`recuperacao.md`, `reranking.md`), apenas a capacidade de armazenamento e busca vetorial + filtros que o banco escolhido deve oferecer.

---

## 3. Candidatos Avaliados

| Candidato | Modelo de implantação | Filtros por metadados | Observações |
|-----------|------------------------|------------------------|-------------|
| **Qdrant** | Servidor dedicado (Docker) **ou** modo embutido/local (biblioteca Python, sem servidor separado, persistência em disco) | Sim, nativo e robusto (filtros complexos, combináveis com busca vetorial) | Boa relação simplicidade/recursos; suporta crescimento futuro sem redesenho caso o modo servidor seja adotado depois |
| **ChromaDB** | Modo embutido (biblioteca Python, roda dentro do próprio processo da aplicação) **ou** servidor dedicado | Sim, suporte a filtros de metadados, mais simples que Qdrant | Extremamente simples de operar em modo embutido; adequado a corpus pequeno e monólito modular |
| **FAISS** | Biblioteca embutida apenas (sem servidor, sem persistência nativa de metadados) | **Não nativo** — FAISS armazena apenas vetores; filtros por metadados exigem construir uma camada própria de mapeamento | Mais rápido em buscas puramente vetoriais, mas exige mais engenharia própria para atender RF-05/RF-06 da visão geral |
| **Milvus** | Requer arquitetura de servidor mais pesada (múltiplos componentes: proxy, coordenadores, storage) | Sim, robusto | Desenhado para escala muito maior que a necessária aqui; contraria a decisão de monólito modular e ausência de orquestrador |
| **pgvector** | Extensão do PostgreSQL — requer um servidor PostgreSQL já operante | Sim, via SQL nativo (JOIN com colunas de metadados) | Interessante se já houver PostgreSQL na infraestrutura; desempenho de busca vetorial pura tende a ficar atrás de bancos vetoriais dedicados em escalas maiores (não crítico aqui) |

---

## 4. Análise Frente às Restrições Confirmadas

* **Sem orquestrador de containers** (`arquitetura.md`): favorece fortemente candidatos com **modo embutido/embarcado** (Qdrant local mode, ChromaDB embutido), que rodam dentro do próprio processo da aplicação monolítica. Milvus é o mais penalizado por essa restrição.
* **Corpus pequeno (<1.000 documentos)**: nenhum candidato terá problema de escala neste volume; a decisão prioriza simplicidade operacional sobre desempenho em escala massiva.
* **Monólito modular confirmado**: reforça a preferência por modo embutido.
* **Filtros por metadados ricos** (RF-05 da visão geral): elimina FAISS puro como opção viável isoladamente.

**Decisão adotada:** **Qdrant em modo embutido/local** — combina filtros de metadados robustos, boa performance, e não exige infraestrutura adicional além do próprio processo da aplicação. Também permite migrar para modo servidor no futuro (mesma API de cliente) caso a escala cresça significativamente, sem exigir reescrita da camada de acesso.

---

## 5. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-VEC-01 | Armazenar vetores de embedding junto com todos os metadados definidos em `enriquecimento.md`/`chunking.md` (payload por chunk). |
| RF-VEC-02 | Suportar busca por similaridade (cosine similarity ou equivalente) combinada com filtros por metadados (ex.: buscar apenas dentro de uma `categoria` específica). |
| RF-VEC-03 | Suportar upsert idempotente por `chunk_id` (reindexação sem duplicação, alinhado a `chunking.md`/`ingestao.md`). |
| RF-VEC-04 | Suportar remoção de todos os chunks associados a um `documento_id` (necessário para RF-09 da visão geral). |
| RF-VEC-05 | Persistir dados em disco de forma durável (sobreviver a reinícios do processo/serviço). |

---

## 6. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-VEC-01 | Operar sem exigir infraestrutura de orquestração adicional (alinhado à decisão confirmada em `arquitetura.md`). |
| RNF-VEC-02 | Latência de busca compatível com uso interativo, folgada dado o corpus pequeno. |
| RNF-VEC-03 | Ser acessível através da porta `VectorStore` (interface abstrata definida em `arquitetura.md`), permitindo troca futura sem impacto em `Retriever`/`Reranker`/`ContextBuilder`. |

---

## 7. Dependências

* Porta `VectorStore` definida em `arquitetura.md`.
* Modelo de embedding e suas dimensões (definido em `embeddings.md`, a confirmar dimensão exata após benchmark) — relevante para configuração do índice vetorial.
* Ambiente de armazenamento em disco disponível na cloud privada para persistência do índice (path local do processo, dado o modo embutido).

---

## 8. Critérios de Aceitação

* [ ] Vetores e metadados completos de cada chunk são armazenados corretamente.
* [ ] Busca por similaridade com filtro de metadados (ex.: por categoria) retorna resultados corretos e relevantes.
* [ ] Upsert por `chunk_id` não gera duplicação ao reprocessar o mesmo documento.
* [ ] Remoção de um documento remove todos os chunks associados corretamente.
* [ ] Dados persistem corretamente após reinício do processo/serviço.
* [ ] Nenhuma infraestrutura de orquestração adicional é necessária para operar (modo embutido).

---

## 9. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Modo embutido pode ter limitações de concorrência (múltiplas escritas simultâneas) | Baixo (corpus pequeno) | Validar em testes de integração; Qdrant suporta migração para modo servidor com a mesma API caso necessário |
| Migração futura para modo servidor (caso a escala cresça) pode exigir esforço de migração de dados | Baixo | Qdrant suporta ambos os modos com API compatível, minimizando esforço de migração futura |
| FAISS teria sido mais rápido em busca pura, mas foi descartado por falta de filtros nativos | Baixo | Aceitável, dado que RF-05 (filtros por metadados) é mais importante que velocidade bruta neste porte de corpus |

---

## 10. Alternativas Avaliadas

Ver seção 3 (tabela comparativa) e seção 4 (análise frente às restrições). Milvus e FAISS puro descartados pelos motivos detalhados. ChromaDB embutido era uma alternativa igualmente viável e mais simples, mas o Qdrant foi preferido por oferecer filtros de metadados mais robustos e um caminho de migração mais suave para modo servidor, caso o projeto cresça além do escopo atual.

---

## 11. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Qdrant em modo embutido/local como `VectorStore` | Melhor equilíbrio entre filtros de metadados robustos, simplicidade operacional (sem orquestrador) e caminho de evolução futura | ✅ Assumido (ver seção 13) |
| Descartar Milvus como candidato | Complexidade operacional incompatível com as restrições confirmadas do projeto | Confirmado |
| Descartar FAISS puro como candidato isolado | Falta de suporte nativo a filtros de metadados, requisito explícito (RF-05 da visão geral) | Confirmado |

---

## 12. Estratégia de Testes

* **Unitários:** operações de upsert, busca com filtro, remoção por `documento_id`, testadas contra a interface `VectorStore`.
* **Integração:** chunking → embeddings → indexação, validando que a busca retorna os chunks esperados.
* **Benchmark leve:** medir latência de indexação/busca do Qdrant embutido com uma amostra do corpus real, como validação (não comparação competitiva, já que a decisão já foi tomada).
* **Regressão:** reindexação do mesmo documento não duplica chunks (upsert idempotente).

---

## 13. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas (preferência de ferramenta; modo embutido vs. serviço separado) |
| 2026-07-04 | Usuário solicitou continuidade sem responder às pendências específicas | **Premissa assumida por Claude**, seguindo a recomendação técnica já indicada na análise (seção 4): Qdrant em modo embutido/local, sem preferência prévia declarada pela equipe |
| 2026-07-04 | **Spec aprovada (v1.0) com premissa assumida** | Liberado avanço para `indexacao.md` |

**⚠️ Esta é uma premissa assumida, não uma confirmação explícita do usuário.** Caso haja preferência por outro banco vetorial (ex.: ChromaDB) ou por rodá-lo como serviço separado em vez de embutido, esta spec deve ser revisada antes da implementação real do módulo `VectorStore`.

---

**Próximo passo:** avançar para `indexacao.md`, detalhando o processo de indexação (upsert, versionamento, atualização incremental).
