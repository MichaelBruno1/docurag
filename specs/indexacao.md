# Especificação: Indexação

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `banco-vetorial.md` (v1.0), `embeddings.md` (v1.0), `chunking.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Definir o processo de indexação: como chunks (com embeddings e metadados já gerados) são persistidos no Qdrant (modo embutido), incluindo estratégia de upsert, versionamento, atualização incremental e remoção — garantindo consistência entre o `document_id`/`chunk_id` lógico e o estado real do índice vetorial.

---

## 2. Escopo

Cobre a orquestração do `IndexDocumentUseCase` / `UpdateDocumentUseCase` / `RemoveDocumentUseCase` (definidos em `arquitetura.md`), consumindo chunks+embeddings e escrevendo no `VectorStore` (Qdrant embutido). Não cobre a geração de embeddings em si (`embeddings.md`) nem a lógica de busca (`recuperacao.md`).

---

## 3. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-IDX-01 | Indexar cada chunk com seu vetor de embedding e payload completo de metadados no Qdrant. |
| RF-IDX-02 | Ao reingerir um documento (upsert por nome de arquivo, conforme `ingestao.md`), remover todos os chunks antigos associados ao `documento_id` antes de indexar os novos, evitando chunks órfãos de versões anteriores. |
| RF-IDX-03 | Suportar remoção completa de um documento (todos os seus chunks) via `documento_id`, atendendo RF-09 da visão geral. |
| RF-IDX-04 | Registrar, nos metadados de cada chunk indexado, a versão do modelo de embedding utilizado (RF-EMB-04 de `embeddings.md`), permitindo identificar chunks indexados com modelos diferentes (relevante se o modelo for trocado no futuro). |
| RF-IDX-05 | A indexação deve ser transacional o suficiente para evitar estado inconsistente: se a indexação de um documento falhar no meio do processo, os chunks parcialmente indexados dessa tentativa devem ser revertidos/limpos, não deixados como lixo no índice. |
| RF-IDX-06 | Expor estatísticas básicas de indexação (total de documentos indexados, total de chunks, última atualização) para o endpoint de estatísticas da API (`api.md`). |

---

## 4. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-IDX-01 | O processo de indexação deve ser idempotente: executar a indexação do mesmo documento múltiplas vezes deve resultar no mesmo estado final no índice (sem duplicatas, sem chunks órfãos). |
| RNF-IDX-02 | Tempo de indexação por documento deve ser medido e reportado (métrica de benchmark: "tempo médio de indexação", conforme `visao-geral.md`). |
| RNF-IDX-03 | A indexação roda como parte do processamento assíncrono definido em `ingestao.md` (fila real — Redis/RabbitMQ), não bloqueando a resposta do upload. |

---

## 5. Estratégia de Upsert e Versionamento

1. Ao processar um documento (novo ou reenviado), o pipeline gera um novo conjunto de chunks a partir do zero (parsing → normalização → enriquecimento → chunking → embeddings).
2. Antes de inserir os novos chunks, o `IndexDocumentUseCase` consulta o Qdrant por todos os chunks existentes com o mesmo `documento_id` e os remove.
3. Os novos chunks são inseridos com seus `chunk_id`s determinísticos (RF-CHUNK-04 de `chunking.md`).
4. Esta abordagem ("remover tudo, reinserir tudo") é mais simples e segura que um diff incremental de chunks — aceitável dado o corpus pequeno (<1.000 documentos) e volume de reingestões esperado ser baixo.

**Nota:** uma estratégia de diff incremental (atualizar apenas chunks que mudaram) traria eficiência marginal em custo computacional, mas adiciona complexidade significativa (comparação de conteúdo por chunk) não justificada pelo porte do projeto — reavaliar apenas se o volume/frequência de reingestão crescer muito no futuro.

---

## 6. Dependências

* `VectorStore` (Qdrant embutido, `banco-vetorial.md`).
* Chunks com embeddings e metadados prontos (saída de `embeddings.md`/`chunking.md`/`enriquecimento.md`).
* Fila de processamento assíncrono (`ingestao.md`).

---

## 7. Critérios de Aceitação

* [ ] Indexar um documento novo insere corretamente todos os seus chunks com embeddings e metadados.
* [ ] Reindexar (upsert) o mesmo documento remove os chunks antigos e insere os novos, sem duplicação nem chunks órfãos.
* [ ] Remover um documento remove todos os seus chunks do índice.
* [ ] Uma falha no meio da indexação não deixa o índice em estado parcialmente corrompido (chunks órfãos de uma tentativa falha).
* [ ] Estatísticas de indexação (total de documentos/chunks) estão disponíveis e corretas.
* [ ] Tempo de indexação por documento é medido e registrado.

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Falha no meio da indexação (ex.: queda do processo) pode deixar chunks parcialmente inseridos | Médio | Remover chunks antigos apenas após confirmar que os novos foram inseridos com sucesso (ordem inversa: inserir novos primeiro, depois remover antigos, usando um campo de "versão" para diferenciar durante a transição) — ver decisão na seção 9 |
| Estratégia "remover tudo, reinserir tudo" pode ser ineficiente se documentos crescerem muito em tamanho/frequência de atualização | Baixo (dado corpus pequeno) | Aceitável para v1; revisar se o cenário de uso mudar significativamente |

---

## 9. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Upsert via "inserir novos chunks primeiro, depois remover os antigos" (não o inverso) | Evita janela de inconsistência onde um documento fica sem nenhum chunk indexado durante a reindexação; mitiga RF-IDX-05 | Proposto |
| Estratégia de reindexação total (não incremental por diff) | Simplicidade justificada pelo corpus pequeno; complexidade de diff não compensa o ganho marginal | Proposto |
| Versionamento do modelo de embedding no payload de cada chunk | Permite identificar e reindexar seletivamente se o modelo de embedding for trocado no futuro | Proposto |

---

## 10. Estratégia de Testes

* **Unitários:** upsert, remoção, geração de estatísticas, testados contra o `VectorStore`.
* **Integração:** pipeline completo (parsing → ... → indexação), validando estado final do índice.
* **Regressão:** reindexação repetida do mesmo documento não altera a contagem final de chunks além do esperado.
* **Testes de falha:** simular falha no meio da indexação (ex.: exceção forçada) e validar que o índice não fica em estado inconsistente.
* **Desempenho:** medir tempo de indexação para documentos de tamanhos variados.

---

## 11. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado e aprovado na mesma revisão (v1.0) | Nenhuma pendência bloqueante identificada — decisões decorrem diretamente das specs já aprovadas (`ingestao.md`, `chunking.md`, `banco-vetorial.md`) |

---

**Próximo passo:** avançar para `recuperacao.md`, detalhando a estratégia de busca (vetorial, híbrida, filtros, deduplicação, expansão de consultas).
