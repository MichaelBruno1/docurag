# Especificação: Visão Geral da Plataforma RAG

**Status:** ✅ Aprovado
**Versão:** 1.0
**Autor:** Principal Software Engineer (Agente)
**Data:** 2026-07-04

---

## 1. Objetivo

Construir uma plataforma de Retrieval-Augmented Generation (RAG) de nível de produção, especializada em fornecer contexto de alta qualidade para modelos LLM locais de **4B a 9B parâmetros**, aplicada ao domínio de **documentação técnica e corporativa interna**.

O sucesso do projeto será medido pela qualidade da recuperação de informação (precisão, relevância, baixo ruído) e não apenas pelo funcionamento técnico do sistema.

---

## 2. Escopo

### 2.1 Incluído no escopo (v1)

* Ingestão de documentos técnicos/corporativos internos nos formatos: PDF, DOCX, XLSX, CSV, TXT, Markdown.
* Pipeline completo: ingestão → extração → limpeza → normalização → enriquecimento → chunking → embeddings → indexação → busca → re-ranking → construção de contexto → resposta da LLM.
* Execução em **cloud privada própria** (infraestrutura controlada pela organização, sem dependência de provedores públicos de IA).
* Banco vetorial e modelos de embedding avaliados para operação local/privada.
* API para upload, indexação, atualização, remoção, consulta, benchmark, estatísticas e monitoramento.
* Módulo de benchmark e avaliação contínua da qualidade de recuperação.
* Observabilidade completa (logs estruturados, métricas, rastreabilidade por consulta).

### 2.2 Fora do escopo (v1) — confirmado

* Suporte multi-idioma: **fora de escopo**. Corpus é exclusivamente em português.
* Alta escala (o corpus inicial é pequeno — ver seção 4.3); arquitetura deve ser escalável, mas otimizações para grande volume (>50k documentos) não são prioridade da v1.
* Multi-tenancy: **fora de escopo**, confirmado.
* Interface gráfica de usuário: **fora de escopo** da v1; apenas API.

**✅ Pontos confirmados pelo usuário (2026-07-04):**
1. Idioma: **exclusivamente português**. Não é necessário suporte multi-idioma na v1.
2. Multi-tenancy: **não necessário**.
3. Interface: **apenas API** na v1 (sem UI própria).
4. Compliance/segurança: **sem requisitos específicos de LGPD ou controle de acesso por documento** nesta fase.
5. Infraestrutura: **há GPU disponível** na cloud privada. A LLM (4B–9B) será servida via **LM Studio**, consumida pela plataforma RAG através de sua API local/rede privada (compatível com padrão OpenAI-like).

---

## 3. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-01 | O sistema deve ingerir documentos nos formatos PDF, DOCX, XLSX, CSV, TXT e Markdown. |
| RF-02 | O sistema deve permitir adicionar novos formatos de ingestão sem modificar componentes existentes (extensibilidade via interface/plugin). |
| RF-03 | O sistema deve extrair texto preservando estrutura semântica (títulos, seções, tabelas, hierarquia). |
| RF-04 | O sistema deve enriquecer cada chunk com metadados (documento, seção, página, categoria, autor, data, idioma, palavras-chave, ID único, relacionamentos). |
| RF-05 | O sistema deve indexar chunks em um banco vetorial com suporte a filtros por metadados. |
| RF-06 | O sistema deve permitir busca vetorial, busca híbrida (quando justificada por métricas) e re-ranking dos resultados. |
| RF-07 | O sistema deve construir um contexto otimizado (sem redundância, sem ruído, dentro do limite de tokens) para envio à LLM. |
| RF-08 | O sistema deve expor API para: upload, indexação, atualização, remoção, consulta, benchmark, estatísticas e monitoramento. |
| RF-09 | O sistema deve permitir atualização e remoção de documentos já indexados, refletindo corretamente no índice vetorial. |
| RF-10 | O sistema deve registrar rastreabilidade completa: quais chunks foram usados para compor cada resposta. |

---

## 4. Requisitos Não Funcionais

### 4.1 Prioritários (dado o uso com LLMs de 4B–9B parâmetros)

| ID | Requisito |
|----|-----------|
| RNF-01 | Máxima precisão de recuperação (Precision@K, Recall@K, MRR, nDCG mensurados). |
| RNF-02 | Mínimo ruído e mínimo contexto necessário enviado à LLM. |
| RNF-03 | Baixa redundância entre chunks recuperados. |
| RNF-04 | Contexto estruturado de forma facilmente interpretável por modelos pequenos. |

### 4.2 Arquitetura e Engenharia

| ID | Requisito |
|----|-----------|
| RNF-05 | Arquitetura modular (Clean Architecture, SOLID, baixo acoplamento, alta coesão). |
| RNF-06 | Componentes substituíveis independentemente (embeddings, banco vetorial, re-ranker, etc.). |
| RNF-07 | Observabilidade completa: logs estruturados, métricas, auditoria. |
| RNF-08 | Testabilidade: unitários, integração, regressão, desempenho, avaliação automática de qualidade RAG. |

### 4.3 Escala e Infraestrutura (assumido a partir das respostas fornecidas)

| ID | Requisito |
|----|-----------|
| RNF-09 | Corpus inicial pequeno (< 1.000 documentos). Arquitetura deve suportar crescimento futuro sem redesenho, mas otimizações de v1 são calibradas para esta escala. |
| RNF-10 | Execução em cloud privada própria — **nenhuma dependência de APIs de terceiros para dados sensíveis** (embeddings, LLM e banco vetorial devem rodar dentro do perímetro privado, a confirmar se há exceções aceitáveis, ex. modelos de embedding via API externa). |
| RNF-11 | Segurança: sem requisitos formais de compliance/LGPD ou controle de acesso por documento nesta fase (confirmado pelo usuário). Recomenda-se ainda assim isolamento de rede básico por estar em ambiente corporativo. |
| RNF-12 | A LLM (4B–9B) é servida via **LM Studio** e consumida através de API compatível com padrão OpenAI (endpoint `/v1/chat/completions` ou equivalente), dentro da cloud privada. |
| RNF-13 | Há GPU disponível na infraestrutura — embeddings e re-ranking podem (e devem, quando vantajoso) utilizar aceleração por GPU. |

---

## 5. Dependências

* Definição do(s) modelo(s) de embedding (spec `embeddings.md` — depende de benchmark).
* Definição do banco vetorial (spec `banco-vetorial.md` — depende de benchmark comparando Qdrant, ChromaDB, FAISS, Milvus, pgvector).
* Definição do(s) modelo(s) LLM local(is) de 4B–9B parâmetros que consumirão o contexto (spec `llm.md`).
* Infraestrutura de cloud privada disponível (especificações de hardware/GPU disponíveis para embeddings e LLM — **a levantar**).
* Conjunto de documentos técnicos/corporativos reais ou representativos para benchmark (spec `benchmark.md`).

---

## 6. Critérios de Aceitação

* [ ] Todos os formatos listados (PDF, DOCX, XLSX, CSV, TXT, MD) são ingeridos com sucesso e sem perda de estrutura semântica relevante.
* [ ] Pipeline completo (ingestão → resposta) funciona de ponta a ponta em ambiente de cloud privada.
* [ ] Métricas de recuperação (Precision@K, Recall@K, MRR, nDCG) são calculadas automaticamente via módulo de benchmark.
* [ ] Conjunto de perguntas de referência (golden set) criado e utilizado para validação contínua.
* [ ] Toda resposta gerada é rastreável até os chunks de origem.
* [ ] Arquitetura permite substituição de qualquer componente (embedding, banco vetorial, chunker, re-ranker) sem alterar os demais módulos.
* [ ] Nenhuma dependência externa de cloud pública é exigida para o funcionamento core do sistema (a menos que explicitamente aprovado como exceção).

---

## 7. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Ambiguidade sobre idioma dos documentos pode levar à escolha errada de modelo de embedding | Alto | Confirmar idioma antes de aprovar spec `embeddings.md` |
| Corpus pequeno pode mascarar problemas de escalabilidade que aparecem depois | Médio | Projetar arquitetura escalável desde o início, mesmo otimizando para escala atual |
| Documentos corporativos podem conter dados sensíveis sem classificação clara | Alto | Levantar requisito de segurança/compliance antes da spec de `ingestão` |
| Falta de definição sobre necessidade de UI pode gerar retrabalho | Baixo | Confirmar escopo de UI antes do planejamento de sprints |
| Modelos de 4B–9B são sensíveis a contexto mal construído (mais que modelos grandes) | Alto | Priorizar spec `construção-contexto.md` com validação rigorosa por benchmark |

---

## 8. Alternativas Avaliadas

*A ser detalhado nas specs técnicas específicas (embeddings, banco vetorial, chunking). Nesta spec de visão geral, registra-se apenas a decisão de escopo:*

* **Cloud privada própria vs. execução 100% local (on-premise sem cloud) vs. cloud pública:** optou-se por cloud privada própria conforme decisão do usuário. Justificativa a documentar: equilíbrio entre controle de dados sensíveis (corporativos internos) e elasticidade de infraestrutura.

---

## 9. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Adotar Clean Architecture com módulos independentes por etapa do pipeline | Permite substituir embeddings, banco vetorial e re-ranker sem impacto cruzado | Proposto |
| Executar toda a stack em cloud privada própria | Requisito confirmado pelo usuário; dados corporativos internos exigem controle de perímetro | Confirmado |
| Dimensionar v1 para corpus pequeno (<1.000 documentos), mas manter design escalável | Corpus atual é pequeno; evita over-engineering prematuro mantendo extensibilidade | Proposto |

*ADRs detalhados serão criados individualmente por decisão técnica relevante (ex.: ADR-001-banco-vetorial, ADR-002-embeddings, etc.) conforme o processo avança.*

---

## 10. Estratégia de Testes

* **Unitários:** cada módulo do pipeline (parsing, chunking, enriquecimento, etc.) testado isoladamente.
* **Integração:** pipeline completo executado ponta a ponta com documentos de teste representativos do domínio corporativo/técnico.
* **Regressão:** golden set de perguntas/respostas de referência, executado a cada alteração relevante.
* **Desempenho:** tempo de indexação e latência de consulta medidos sob carga compatível com corpus pequeno-médio.
* **Qualidade de recuperação:** Precision@K, Recall@K, MRR, nDCG calculados automaticamente pelo módulo de benchmark.
* **Qualidade final:** comparação de respostas da LLM (4B–9B) usando diferentes estratégias de chunking/embeddings/recuperação.

---

## 11. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Pendências resolvidas pelo usuário | Português-only, sem multi-tenancy, API-only, sem requisitos LGPD, GPU disponível + LM Studio |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `arquitetura.md` |

---

**Próximo passo:** iniciar `specs/arquitetura.md`, detalhando a arquitetura de referência (camadas, componentes, fluxo de dados), já considerando integração com LM Studio como serviço de inferência da LLM.
