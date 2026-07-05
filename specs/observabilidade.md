# Especificação: Observabilidade

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `arquitetura.md` (v1.0), `api.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Garantir rastreabilidade completa de cada consulta (RF-10 da visão geral) através de logs estruturados, métricas operacionais e auditoria — permitindo depurar problemas de qualidade de recuperação e monitorar a saúde do sistema, mesmo sem orquestrador de containers ou stack de observabilidade complexa.

---

## 2. Escopo

Cobre logging estruturado, métricas expostas via `/v1/metrics` (`api.md`), e o mecanismo de rastreamento por `trace_id` propagado por todas as camadas. Não cobre a definição de métricas de qualidade de recuperação em si (essas são definidas em `benchmark.md`) — aqui se define apenas a infraestrutura de coleta e exposição.

---

## 3. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-OBS-01 | Gerar um `trace_id` único no início de cada consulta/operação, propagado por todas as camadas (ingestão, indexação, recuperação, re-ranking, construção de contexto, LLM). |
| RF-OBS-02 | Registrar logs estruturados (formato JSON) em cada etapa relevante do pipeline, incluindo: timestamp, `trace_id`, etapa, duração, e resultado (sucesso/erro). |
| RF-OBS-03 | Para cada consulta (`/v1/query`), registrar: chunks recuperados (com scores), chunks descartados por orçamento de tokens, chunks re-ranqueados, contexto final enviado à LLM, e resposta gerada — rastreabilidade total, consultável via `/v1/query/{trace_id}` (`api.md`). |
| RF-OBS-04 | Expor métricas operacionais (contagem de requisições, latência por endpoint, taxa de erro, uso de fila) em formato compatível com Prometheus via `/v1/metrics`. |
| RF-OBS-05 | Registrar métricas específicas de RAG mencionadas em `visao-geral.md`: tempo médio de indexação, tempo médio de recuperação, latência total de consulta, quantidade média de tokens enviados por consulta. |
| RF-OBS-06 | Logs de erro devem incluir contexto suficiente para depuração (etapa, `trace_id`, mensagem de erro) sem vazar dados sensíveis do conteúdo dos documentos nos logs (mesmo sem requisito formal de compliance, é boa prática). |

---

## 4. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-OBS-01 | A stack de observabilidade deve ser simples, consistente com a ausência de orquestrador de containers e o monólito modular confirmados (`arquitetura.md`) — evitar dependências pesadas (ex.: stack ELK completa) desnecessárias para o porte do projeto. |
| RNF-OBS-02 | Logs devem ser armazenados de forma persistente (arquivo local com rotação, ou serviço de log simples), sobrevivendo a reinícios do processo. |
| RNF-OBS-03 | Overhead de logging/métricas não deve degradar significativamente a latência do pipeline principal. |

---

## 5. Proposta de Stack de Observabilidade

Dado o porte do projeto (corpus pequeno, monólito modular, sem orquestrador), propõe-se uma stack minimalista:

* **Logs estruturados:** biblioteca de logging estruturado em JSON (ex.: `structlog` em Python), gravando em arquivo local com rotação (ex.: `logrotate` ou rotação nativa da biblioteca), sem exigir um serviço de agregação de logs separado na v1.
* **Métricas:** biblioteca de métricas compatível com Prometheus (ex.: `prometheus-client` em Python), expostas via endpoint `/v1/metrics`; a coleta/visualização (Prometheus + Grafana) fica a critério da infraestrutura existente da organização — esta spec garante apenas que a aplicação **expõe** as métricas no formato correto.
* **Rastreamento (`trace_id`):** implementado via contexto propagado internamente (ex.: `contextvars` em Python), sem necessidade de uma ferramenta de tracing distribuído completa (ex.: Jaeger/OpenTelemetry) dado que a aplicação é um monólito (não há múltiplos serviços para rastrear entre si, exceto a chamada externa ao LM Studio).

---

## 6. Dependências

* Todos os módulos do pipeline devem aceitar e propagar `trace_id` (requisito transversal já mencionado em várias specs anteriores).
* `/v1/metrics` (endpoint definido em `api.md`).

---

## 7. Critérios de Aceitação

* [ ] Toda consulta gera um `trace_id` único, propagado e registrado em todas as etapas.
* [ ] `/v1/query/{trace_id}` retorna o detalhe completo de uma consulta (chunks, scores, contexto, resposta).
* [ ] `/v1/metrics` expõe métricas em formato Prometheus, incluindo as métricas específicas de RAG (seção 3, RF-OBS-05).
* [ ] Logs persistem após reinício do processo.
* [ ] Logs de erro não expõem conteúdo sensível de documentos, apenas metadados e mensagens de erro.

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Logging excessivamente verboso pode gerar grande volume de dados desnecessários | Baixo | Definir níveis de log (INFO para operações normais, DEBUG para detalhes de recuperação, ERROR para falhas) configuráveis |
| Ausência de ferramenta de agregação/visualização de logs pode dificultar análise em produção | Baixo (aceitável dado o porte do projeto) | Logs estruturados em JSON permitem análise posterior com ferramentas simples (ex.: `jq`) mesmo sem stack de agregação; pode evoluir para tal se necessário |

---

## 9. Alternativas Avaliadas

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| Stack completa (ELK/Loki + Prometheus + Grafana + Jaeger) | Observabilidade robusta e escalável | Complexidade operacional alta, exigiria orquestrador (contraria decisão já confirmada) | Rejeitado para v1 |
| Stack minimalista (logs estruturados em arquivo + métricas Prometheus expostas via endpoint) | Simples, sem dependências de infraestrutura adicional, adequado ao monólito modular | Menos poder de análise/visualização out-of-the-box | **Proposto para v1** |

---

## 10. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Logging estruturado em JSON, gravado em arquivo local com rotação | Simplicidade, alinhado à ausência de orquestrador | Proposto |
| Métricas expostas via endpoint compatível Prometheus, sem stack de coleta própria | A aplicação expõe; a infraestrutura de coleta/visualização fica a critério da organização | Proposto |
| `trace_id` propagado via `contextvars`, sem tracing distribuído completo | Aplicação é monólito; overhead de uma ferramenta de tracing completa não se justifica | Proposto |

---

## 11. Estratégia de Testes

* **Unitários:** geração e propagação de `trace_id`, formatação de logs estruturados.
* **Integração:** consulta completa gera registro completo e consultável via `/v1/query/{trace_id}`.
* **Testes de carga leve:** validar que overhead de logging/métricas não degrada significativamente a latência.

---

## 12. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado e aprovado na mesma revisão (v1.0) | Nenhuma pendência bloqueante; stack minimalista pode ser integrada a ferramentas já existentes na organização, se houver |

---

**Próximo passo:** avançar para `testes.md`, detalhando a estratégia de testes e a construção do golden set de perguntas de referência.
