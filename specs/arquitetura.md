# Especificação: Arquitetura da Plataforma RAG

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `visao-geral.md` (aprovada, v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Definir a arquitetura de referência da plataforma RAG: camadas, componentes, fronteiras de responsabilidade, contratos entre módulos e fluxo de dados — garantindo baixo acoplamento, alta coesão e substituibilidade de qualquer componente técnico (embeddings, banco vetorial, chunker, re-ranker, LLM).

---

## 2. Escopo

Cobre a arquitetura de software (camadas, módulos, contratos/interfaces) e a topologia de infraestrutura (serviços, comunicação entre eles) dentro da cloud privada com GPU disponível. Não cobre detalhes internos de cada módulo (chunking, embeddings, etc.) — esses são especificados em documentos próprios (`chunking.md`, `embeddings.md`, etc.), que devem respeitar os contratos definidos aqui.

---

## 3. Estilo Arquitetural

* **Clean Architecture** com separação em camadas: Domínio → Aplicação (casos de uso) → Infraestrutura (adaptadores) → Interface (API).
* **Dependency Injection** para desacoplar módulos de suas implementações concretas.
* **Ports & Adapters (Hexagonal)**: cada componente técnico substituível (embedding provider, vector store, LLM provider, re-ranker) é definido como uma *porta* (interface), com *adaptadores* concretos plugáveis.
* **Pipeline orientado a estágios**, onde cada estágio é um módulo independente, testável isoladamente, comunicando-se por contratos de dados bem definidos (não por acoplamento direto de implementação).

---

## 4. Camadas

### 4.1 Domínio
Entidades e regras de negócio puras, sem dependência de frameworks ou infraestrutura:
* `Document`, `Chunk`, `Metadata`, `QueryResult`, `RetrievalContext`, `Citation`.

### 4.2 Aplicação (Casos de Uso)
Orquestra o pipeline sem conhecer detalhes de implementação:
* `IngestDocumentUseCase`
* `IndexDocumentUseCase`
* `UpdateDocumentUseCase`
* `RemoveDocumentUseCase`
* `QueryUseCase` (busca → re-ranking → construção de contexto)
* `RunBenchmarkUseCase`

### 4.3 Infraestrutura (Adaptadores)
Implementações concretas das portas definidas pelo domínio/aplicação:
* Parsers por formato (PDF, DOCX, XLSX, CSV, TXT, MD)
* Provedor de embeddings (adaptador plugável)
* Vector store (adaptador plugável — Qdrant, ChromaDB, etc., a decidir em `banco-vetorial.md`)
* Adaptador do **LM Studio** (cliente HTTP compatível com API estilo OpenAI, para inferência da LLM 4B–9B)
* Re-ranker (adaptador plugável)
* Armazenamento de metadados/documentos originais

### 4.4 Interface (API)
Camada HTTP que expõe os casos de uso via endpoints REST (detalhado em `api.md`). Não contém lógica de negócio — apenas tradução de requisição/resposta.

---

## 5. Portas (Interfaces) Principais

| Porta | Responsabilidade | Especificação relacionada |
|-------|-------------------|----------------------------|
| `DocumentParser` | Extrair texto/estrutura de um formato específico | `parsing.md` |
| `TextNormalizer` | Limpeza e normalização de texto extraído | `normalizacao.md` |
| `Enricher` | Gerar metadados ricos por chunk | `enriquecimento.md` |
| `Chunker` | Dividir documento normalizado em chunks | `chunking.md` |
| `EmbeddingProvider` | Gerar vetores de embedding para chunks/queries | `embeddings.md` |
| `VectorStore` | Persistir e buscar vetores + metadados | `banco-vetorial.md` |
| `Retriever` | Orquestrar busca (vetorial/híbrida) + filtros | `recuperacao.md` |
| `Reranker` | Reordenar resultados por relevância | `reranking.md` |
| `ContextBuilder` | Montar contexto final otimizado para a LLM | `construcao-contexto.md` |
| `LLMProvider` | Enviar prompt+contexto ao LM Studio e obter resposta | `llm.md` |
| `BenchmarkRunner` | Executar avaliações automatizadas de qualidade | `benchmark.md` |

Cada porta é uma interface abstrata; adaptadores concretos são escolhidos por configuração (injeção de dependência), permitindo trocar, por exemplo, o `VectorStore` de Qdrant para ChromaDB sem alterar `Retriever`, `Reranker` ou `ContextBuilder`.

---

## 6. Topologia de Infraestrutura (Cloud Privada)

**Confirmado pelo usuário:** sem orquestrador de containers (nem Docker Compose, nem Kubernetes). Deployment assumido como serviços rodando diretamente na infraestrutura da cloud privada (processos/containers Docker isolados, geridos manualmente ou via scripts próprios, sem camada de orquestração). **⚠️ Premissa a validar**: caso o usuário pretenda usar containers Docker individuais sem Compose, ou processos nativos sem containerização alguma, isso deve ser esclarecido na spec de deployment/observabilidade — por ora, assumimos containers Docker isolados geridos manualmente.

Serviços previstos:

1. **Serviço de API** (aplicação principal — camadas Aplicação + Interface)
2. **Vector Store** (serviço dedicado — Qdrant/ChromaDB/outro, a definir)
3. **LM Studio** (serviço externo à aplicação, rodando na GPU disponível, exposto via rede privada)
4. **Serviço de Embeddings** — **confirmado: compartilha a mesma GPU do LM Studio** (não haverá GPU dedicada). Isso é um requisito importante para `embeddings.md`: o modelo de embedding escolhido deve ter footprint de VRAM compatível com a coexistência com a LLM 4B–9B no LM Studio, e a spec de embeddings deve considerar estratégias de gerenciamento de contenção (ex.: carregar/descarregar modelo, batching, ou rodar embeddings em CPU se a VRAM for insuficiente durante picos de uso da LLM).
5. **Armazenamento de documentos originais** (filesystem/object storage privado)
6. **Stack de observabilidade** (logs estruturados + métricas — ferramenta a definir em `observabilidade.md`)

---

## 7. Fluxo de Dados (Resumo)

```
[Upload via API]
     ↓
IngestDocumentUseCase
     ↓
DocumentParser (por formato)
     ↓
TextNormalizer
     ↓
Enricher (metadados)
     ↓
Chunker
     ↓
EmbeddingProvider
     ↓
VectorStore (indexação)

[Consulta via API]
     ↓
QueryUseCase
     ↓
Retriever (busca vetorial/híbrida + filtros)
     ↓
Reranker
     ↓
ContextBuilder (contexto otimizado)
     ↓
LLMProvider (LM Studio)
     ↓
Resposta + rastreabilidade (chunks utilizados)
```

---

## 8. Requisitos Não Funcionais Relevantes à Arquitetura

* Qualquer componente (embedding, vector store, chunker, re-ranker) deve ser substituível via configuração, sem alteração de código nos módulos consumidores (RNF-06 da visão geral).
* A comunicação com o LM Studio deve ser abstraída por um adaptador (`LLMProvider`), permitindo trocar o motor de inferência no futuro sem impacto nos demais módulos.
* Toda consulta deve gerar um identificador de rastreamento (`trace_id`) propagado por todas as camadas, permitindo auditoria completa (RF-10).

---

## 9. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Acoplamento acidental entre camadas de domínio e infraestrutura | Alto | Revisão de código focada em dependências; testes de arquitetura (ex.: import-linter) |
| Indefinição sobre orquestração de containers (Compose vs K8s) | Médio | Definir antes da spec de deployment/observabilidade |
| Contenção de GPU entre LM Studio e serviço de embeddings | Médio-Alto | **Confirmado que GPU será compartilhada.** `embeddings.md` deve escolher modelo com footprint de VRAM compatível e/ou estratégia de fallback para CPU sob contenção; validar via benchmark de uso concorrente de GPU. |
| Ausência de UI pode dificultar debug/operação manual | Baixo | Garantir que a API exponha endpoints de estatísticas/monitoramento suficientes (RF-08) |

---

## 10. Alternativas Avaliadas

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| Monólito modular (um único serviço, módulos internos bem separados) | Simplicidade operacional, adequado a corpus pequeno | Menos isolamento de falhas | **✅ Confirmado para v1** pelo usuário |
| Microsserviços por estágio do pipeline | Escalabilidade e isolamento máximos | Complexidade operacional desnecessária para o volume atual | Rejeitado para v1; pode ser revisitado se escala crescer |

---

## 11. Critérios de Aceitação

* [ ] Todas as portas (interfaces) estão documentadas e não vazam detalhes de implementação para a camada de aplicação/domínio.
* [ ] É possível trocar o `VectorStore` ou `EmbeddingProvider` alterando apenas configuração/injeção de dependência.
* [ ] O adaptador `LLMProvider` se comunica corretamente com o LM Studio via API compatível OpenAI.
* [ ] Toda consulta é rastreável via `trace_id` de ponta a ponta.
* [ ] Arquitetura documentada permite que qualquer novo desenvolvedor entenda o fluxo completo sem necessidade de ler o código-fonte.

---

## 12. Estratégia de Testes

* Testes de arquitetura (verificação automática de que camadas de domínio não importam infraestrutura).
* Testes de contrato para cada porta (garantindo que qualquer adaptador futuro respeite a interface).
* Testes de integração do pipeline completo usando adaptadores "fake"/in-memory (sem depender de GPU/LM Studio real) para CI rápido.
* Testes de integração real (end-to-end) contra LM Studio e vector store reais, executados em ambiente de staging.

---

## 13. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Decisões confirmadas pelo usuário | Sem orquestrador de containers; GPU compartilhada entre embeddings e LM Studio; monólito modular confirmado |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `ingestao.md` |

**⚠️ Nota para revisão futura:** o modelo de deployment sem orquestrador (nem Compose, nem K8s) precisa ser detalhado na spec de observabilidade/deployment — especificamente como os serviços (API, vector store, LM Studio, embeddings) serão executados, reiniciados e monitorados na prática.

---

**Próximo passo:** avançar para `ingestao.md`, detalhando o primeiro estágio do pipeline (upload, validação inicial, roteamento por formato).
