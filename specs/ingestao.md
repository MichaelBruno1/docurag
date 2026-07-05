# Especificação: Ingestão de Documentos

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `visao-geral.md` (v1.0), `arquitetura.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Definir o primeiro estágio do pipeline: recebimento, validação inicial e roteamento de documentos para o parser correto, garantindo que apenas documentos válidos e suportados entrem no pipeline de processamento.

---

## 2. Escopo

Cobre: recebimento via API (upload), validação de formato/integridade, atribuição de identificador único ao documento, armazenamento do arquivo original, e roteamento para o `DocumentParser` apropriado (porta definida em `arquitetura.md`).

Não cobre: extração de texto em si (spec `parsing.md`), nem limpeza/normalização (spec `normalizacao.md`).

---

## 3. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-ING-01 | Aceitar upload de arquivos nos formatos PDF, DOCX, XLSX, CSV, TXT, Markdown via API. |
| RF-ING-02 | Validar a extensão declarada contra o conteúdo real do arquivo (magic bytes/MIME sniffing), rejeitando arquivos incompatíveis ou corrompidos. |
| RF-ING-03 | Atribuir um identificador único (UUID) a cada documento ingerido. |
| RF-ING-04 | Armazenar o arquivo original em armazenamento persistente antes de iniciar o processamento (garantia de idempotência/reprocessamento). |
| RF-ING-05 | Registrar metadados iniciais do documento: nome original, formato, tamanho, timestamp de upload, `trace_id`. |
| RF-ING-06 | Rotear o documento para o `DocumentParser` correspondente ao seu formato, com base no adaptador configurado (RNF-06 da arquitetura). |
| RF-ING-07 | **Confirmado:** reenviar um arquivo com o **mesmo nome** de um documento já existente realiza **upsert automático** — a versão anterior é invalidada/substituída no índice (relacionado a RF-09 da visão geral), sem exigir identificador explícito na API. |
| RF-ING-08 | **Confirmado:** rejeitar arquivos que excedam **50MB**, retornando erro claro ao cliente da API (ex.: HTTP 413). |
| RF-ING-09 | Emitir evento/log estruturado a cada etapa da ingestão (recebido, validado, armazenado, roteado, erro), propagando o `trace_id`. |

---

## 4. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-ING-01 | A ingestão deve ser assíncrona em relação ao restante do pipeline — o upload retorna rapidamente (aceito/enfileirado), e o processamento pesado ocorre em background. |
| RNF-ING-02 | A ingestão deve ser idempotente: reenviar o mesmo arquivo não deve gerar duplicação silenciosa de dados. |
| RNF-ING-03 | Falhas de ingestão de um documento não devem afetar a ingestão de outros documentos em processamento simultâneo. |
| RNF-ING-04 | **Confirmado:** será utilizada uma **fila real** (Redis ou RabbitMQ, a decidir tecnicamente) para processamento assíncrono, mesmo com corpus pequeno — garante resiliência a reinícios do processo e melhor rastreabilidade de jobs em andamento. |

---

## 5. Dependências

* Porta `DocumentParser` definida em `arquitetura.md`.
* Definição de onde/como o arquivo original é armazenado (object storage privado, conforme `arquitetura.md` seção 6, item 5).
* Estratégia de fila/processamento assíncrono — a confirmar mecanismo concreto (ver pendência abaixo).

---

## 6. Critérios de Aceitação

* [ ] Upload de arquivo em cada um dos 6 formatos suportados é aceito, validado e roteado corretamente.
* [ ] Upload de arquivo com extensão incompatível com o conteúdo real é rejeitado com mensagem de erro clara.
* [ ] Upload de arquivo corrompido é rejeitado sem quebrar o serviço de API.
* [ ] Reenvio do mesmo documento (reingestão) atualiza corretamente a versão indexada, sem duplicar chunks.
* [ ] Cada operação de ingestão gera logs estruturados rastreáveis por `trace_id`.
* [ ] Upload acima do tamanho máximo configurado é rejeitado com código de erro apropriado (ex.: HTTP 413).

---

## 7. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Arquivos malformados/corrompidos derrubando o parser | Alto | Validação de integridade antes do roteamento; parsing isolado (try/catch por documento, nunca falha em cascata) |
| Reingestão gerando chunks duplicados no vector store | Alto | Estratégia clara de versionamento/invalidação por nome de arquivo antes de reindexar |
| **Upsert automático por nome de arquivo pode causar sobrescrita indevida** se dois documentos distintos tiverem o mesmo nome (ex.: "relatorio.pdf" de contextos diferentes) | Médio | Recomenda-se, na prática operacional, orientar usuários a usar nomes de arquivo únicos/descritivos; considerar alerta ou log de auditoria quando um upsert substitui um documento existente |
| Ausência de fila real pode limitar throughput em picos de upload | Baixo (dado corpus pequeno) | Interface desacoplada permite evoluir para fila real sem retrabalho nos casos de uso |

---

## 8. Alternativas Avaliadas

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| Processamento síncrono (upload bloqueia até indexação completa) | Simplicidade máxima | Timeout em documentos grandes; má experiência de API | Rejeitado |
| Fila em memória/processo único | Simples, sem infraestrutura adicional | Não sobrevive a reinício do processo; jobs em andamento são perdidos | Rejeitado |
| Fila real (Redis/RabbitMQ) | Resiliente a reinícios, rastreável, permite retry de jobs | Adiciona um serviço à infraestrutura | **✅ Confirmado para v1** |

---

## 9. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Ingestão assíncrona com **fila real** (Redis/RabbitMQ, a decidir tecnicamente) | Resiliência a reinícios do processo mesmo com corpus pequeno; requisito explícito do usuário | ✅ Confirmado |
| Validação de conteúdo real (magic bytes) além da extensão | Evita falhas silenciosas de parsing por arquivos malformados | Proposto |
| **Upsert automático por nome de arquivo** (sem identificador explícito na API) | Simplicidade de uso para o cliente da API; alinhado a RF-09 da visão geral | ✅ Confirmado |

---

## 10. Estratégia de Testes

* **Unitários:** validação de formato/integridade para cada tipo de arquivo suportado; geração de UUID; roteamento correto por formato.
* **Integração:** upload real via API → armazenamento → roteamento para parser correto (usando parsers "fake" para isolar do estágio de extração).
* **Regressão:** conjunto de arquivos de teste incluindo casos válidos, corrompidos, extensão incorreta, e tamanho excedido.
* **Desempenho:** tempo de resposta do endpoint de upload sob concorrência (múltiplos uploads simultâneos, mesmo com corpus pequeno).

---

## 11. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Decisões confirmadas pelo usuário | Fila real (Redis/RabbitMQ) em vez de fila em memória; limite de 50MB por upload; upsert automático por nome de arquivo |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `parsing.md` |

**⚠️ Nota para revisão futura:** a escolha técnica entre Redis e RabbitMQ ainda não foi feita — deve ser decidida (com justificativa) ao detalhar a implementação, considerando o que já está disponível na infraestrutura da cloud privada.

---

**Próximo passo:** avançar para `parsing.md`, detalhando a extração de texto/estrutura por formato (PDF, DOCX, XLSX, CSV, TXT, MD).
