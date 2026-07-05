# Especificação: API

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `arquitetura.md` (v1.0), `ingestao.md` (v1.0), `llm.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Projetar os endpoints REST que expõem os casos de uso da plataforma (upload, indexação, atualização, remoção, consulta, benchmark, estatísticas, monitoramento), conforme `visao-geral.md` e `arquitetura.md` — como **única interface** da v1 (confirmado: sem UI própria).

---

## 2. Escopo

Cobre o design dos endpoints HTTP, contratos de requisição/resposta, códigos de status e autenticação básica. Não cobre a lógica de negócio em si (implementada nos casos de uso já especificados nas demais specs).

---

## 3. Endpoints Propostos

### 3.1 Ingestão e Gestão de Documentos

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/v1/documents` | Upload de um novo documento (multipart/form-data). Realiza upsert automático por nome de arquivo (`ingestao.md`). Retorna `202 Accepted` com `documento_id` e status "enfileirado". |
| `GET` | `/v1/documents` | Lista documentos indexados, com paginação e filtros por metadados (categoria, data, etc.). |
| `GET` | `/v1/documents/{documento_id}` | Detalhes de um documento específico (metadados, status de processamento, contagem de chunks). |
| `GET` | `/v1/documents/{documento_id}/status` | Status de processamento assíncrono (enfileirado, processando, concluído, erro) — necessário dado que a ingestão é assíncrona (`ingestao.md`). |
| `DELETE` | `/v1/documents/{documento_id}` | Remove um documento e todos os seus chunks do índice (RF-09 da visão geral). |

### 3.2 Consulta

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/v1/query` | Recebe uma pergunta do usuário, executa o pipeline completo de recuperação → re-ranking → construção de contexto → LLM, retorna a resposta + chunks usados (rastreabilidade) + `trace_id`. Suporta filtros opcionais por metadados (ex.: restringir a uma categoria). |
| `GET` | `/v1/query/{trace_id}` | Recupera o detalhe de uma consulta já realizada (para auditoria/depuração), incluindo chunks recuperados, scores, e contexto final enviado à LLM. |

### 3.3 Benchmark e Qualidade

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/v1/benchmark/run` | Executa o golden set de perguntas de referência (`testes.md`) contra a configuração atual, retornando métricas (Precision@K, Recall@K, MRR, nDCG). |
| `GET` | `/v1/benchmark/results` | Lista execuções de benchmark anteriores, para acompanhar evolução da qualidade ao longo do tempo. |

### 3.4 Estatísticas e Monitoramento

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/v1/stats` | Estatísticas gerais: total de documentos, total de chunks, tamanho do índice, última atualização (RF-IDX-06 de `indexacao.md`). |
| `GET` | `/v1/health` | Health check: status da aplicação, conectividade com Qdrant (embutido, verificação interna) e com o LM Studio. |
| `GET` | `/v1/metrics` | Métricas operacionais no formato compatível com sistemas de observabilidade (ex.: Prometheus), conforme `observabilidade.md`. |

---

## 4. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-API-01 | Expor todos os endpoints da seção 3 seguindo convenções REST (verbos HTTP corretos, códigos de status apropriados). |
| RF-API-02 | Upload de documento (RF-API endpoint `/v1/documents`) deve validar tamanho (50MB, `ingestao.md`) e retornar erro claro (HTTP 413) se excedido. |
| RF-API-03 | `/v1/query` deve retornar, além da resposta textual, a lista de chunks usados com suas referências de origem (documento/seção), permitindo ao cliente da API construir citações. |
| RF-API-04 | Todos os endpoints devem propagar/gerar `trace_id` para rastreabilidade, incluído na resposta. |
| RF-API-05 | Erros devem retornar corpo JSON estruturado com código de erro, mensagem clara, e `trace_id` (quando aplicável), evitando vazar detalhes internos sensíveis (stack traces) nas respostas. |
| RF-API-06 | `/v1/documents` (GET) e `/v1/benchmark/results` devem suportar paginação (para escalar graciosamente conforme o corpus/histórico cresce). |

---

## 5. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-API-01 | A API é a **única interface** da v1 (confirmado: sem UI própria) — deve ser suficientemente completa e bem documentada (ex.: OpenAPI/Swagger) para uso direto por outros sistemas/scripts internos. |
| RNF-API-02 | Autenticação básica (ex.: API key) deve proteger os endpoints, mesmo sem requisitos formais de compliance/LGPD (`visao-geral.md`) — trata-se de boa prática mínima de segurança, não de conformidade regulatória. |
| RNF-API-03 | `/v1/query` deve ter timeout configurável, considerando que o pipeline completo (recuperação + re-ranking + LLM) pode levar alguns segundos. |

---

## 6. Dependências

* Todos os casos de uso definidos em `arquitetura.md` (`IngestDocumentUseCase`, `QueryUseCase`, etc.).
* Fila de processamento assíncrono (`ingestao.md`) para status de documentos.
* Especificação de observabilidade (`observabilidade.md`) para o formato de `/v1/metrics`.

---

## 7. Critérios de Aceitação

* [ ] Todos os endpoints da seção 3 estão implementados e documentados (OpenAPI/Swagger).
* [ ] Upload, consulta, remoção e estatísticas funcionam ponta a ponta.
* [ ] Erros retornam corpo estruturado e código de status apropriado, sem vazar detalhes internos.
* [ ] Autenticação básica (API key) protege todos os endpoints, exceto `/v1/health` (tipicamente público para checagem de infraestrutura).
* [ ] `/v1/query` retorna resposta + chunks usados + `trace_id` corretamente.

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Ausência de UI pode dificultar debug/operação manual por usuários não técnicos | Baixo (já aceito em `visao-geral.md`) | Garantir documentação OpenAPI clara e endpoints de estatísticas/monitoramento suficientes para uso via ferramentas como Postman/curl |
| API key simples pode ser insuficiente se o uso crescer para múltiplos sistemas/times | Baixo (sem requisito de compliance) | Suficiente para v1; revisar modelo de autenticação se o cenário de uso mudar |

---

## 9. Alternativas Avaliadas

*Não há alternativas arquiteturais relevantes a avaliar nesta spec — a decisão de expor apenas API REST (sem UI) já foi confirmada em `visao-geral.md`. A escolha de autenticação simples (API key) versus OAuth2/mTLS mais complexos foi descartada como over-engineering, dado que não há requisito de compliance/multi-tenancy.*

---

## 10. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| API REST como única interface, com documentação OpenAPI | Confirmado em `visao-geral.md`; suficiente para uso corporativo interno via scripts/integrações | Proposto |
| Autenticação via API key simples | Proporcional ao risco (sem multi-tenancy, sem compliance formal exigido) | Proposto |
| Endpoint de status assíncrono (`/v1/documents/{id}/status`) | Necessário dado que a ingestão é assíncrona (fila real confirmada em `ingestao.md`) | Proposto |

---

## 11. Estratégia de Testes

* **Unitários:** validação de payloads, códigos de status por cenário (sucesso, erro, não encontrado).
* **Integração:** fluxo completo via API (upload → consulta → verificação de resposta) em ambiente de teste.
* **Contrato:** validar que a API segue a especificação OpenAPI publicada (testes de contrato automatizados).
* **Segurança básica:** validar que endpoints protegidos rejeitam requisições sem API key válida.

---

## 12. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado e aprovado na mesma revisão (v1.0) | Nenhuma pendência bloqueante; ajustes de nomenclatura de endpoints podem ser feitos sem impacto nas demais specs |

---

**Próximo passo:** avançar para `observabilidade.md`, detalhando logs estruturados, métricas e auditoria.
