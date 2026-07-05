# Especificação: Testes

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** Todas as specs de pipeline (`ingestao.md` a `llm.md`)
**Data:** 2026-07-04

---

## 1. Objetivo

Consolidar a estratégia de testes da plataforma (unitários, integração, regressão, desempenho, recuperação, avaliação automática de qualidade) e definir o processo de construção do **golden set de perguntas de referência** — mencionado como dependência em várias specs anteriores (`chunking.md`, `recuperacao.md`, `reranking.md`, `construcao-contexto.md`, `llm.md`) e que ainda não havia sido detalhado.

---

## 2. Escopo

Cobre a estratégia de testes transversal a todo o pipeline e o processo de criação/manutenção do golden set. Não cobre as métricas específicas de benchmark em si (essas são detalhadas em `benchmark.md`) — aqui se define o **conjunto de dados de teste** que alimenta o benchmark.

---

## 3. Golden Set de Perguntas de Referência

### 3.1 Processo de Construção

Conforme identificado em `chunking.md`, o golden set precisa ser construído **antes** de finalizar decisões como tamanho de chunk. **Processo confirmado: semi-automatizado (geração via LLM + revisão humana).**

1. Selecionar uma amostra representativa do corpus real (documentação técnica/corporativa) — recomenda-se cobrir os principais tipos de documento (manuais, políticas, procedimentos, especificações) identificados na taxonomia de `enriquecimento.md`.
2. **Usar o próprio `qwen/qwen3.5-9b` (via LM Studio) para gerar perguntas candidatas** a partir de cada documento da amostra, com um prompt específico pedindo perguntas realistas que um usuário faria, junto com a resposta esperada extraída do texto.
3. **Revisão humana obrigatória** de cada pergunta/resposta gerada, antes de incluí-la no golden set — a LLM gera candidatos, mas não decide sozinha o que entra no conjunto de referência (evita viés circular: usar a mesma LLM para gerar e depois "validar a si mesma" sem supervisão).
4. Para cada pergunta aprovada, registrar: a pergunta, a resposta esperada (ou os pontos-chave que a resposta deve conter), e o(s) chunk(s)/trecho(s) de origem esperados (ground truth para métricas de recuperação) — identificados manualmente na revisão, não apenas confiados à geração automática.
5. Incluir também perguntas "negativas" (cuja resposta **não** está no corpus) — estas devem ser criadas manualmente ou cuidadosamente revisadas, já que pedir à LLM para gerar "perguntas sem resposta" é menos direto que gerar perguntas com resposta.
6. **Meta confirmada: 30 perguntas** para a primeira versão do golden set; expandir iterativamente conforme o projeto evolui.

### 3.2 Manutenção

* O golden set deve ser versionado (ex.: arquivo JSON/YAML versionado em controle de versão), permitindo rastrear mudanças ao longo do tempo.
* Deve ser expandido sempre que uma lacuna de cobertura for identificada (ex.: um tipo de documento novo adicionado ao corpus).
* Perguntas cuja resposta esperada mudar (ex.: documento atualizado) devem ser revisadas para manter a validade do golden set.

---

## 4. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-TEST-01 | Criar e manter um golden set versionado de **30 perguntas** de referência (meta confirmada), cobrindo os principais tipos de documento do corpus, gerado via processo semi-automatizado (LLM + revisão humana). |
| RF-TEST-02 | Cada pergunta do golden set deve ter: pergunta, resposta esperada/pontos-chave, e chunks/trechos de origem esperados (ground truth) — identificados/confirmados na revisão humana, mesmo quando a pergunta é gerada automaticamente. |
| RF-TEST-03 | Incluir perguntas negativas (sem resposta no corpus) para validar grounding/honestidade da LLM — criadas ou cuidadosamente revisadas manualmente, dado que a geração automática de perguntas "sem resposta" é menos confiável. |
| RF-TEST-04 | Implementar suíte de testes unitários para cada módulo do pipeline (parsing, normalização, enriquecimento, chunking, embeddings, indexação, recuperação, re-ranking, construção de contexto, LLM). |
| RF-TEST-05 | Implementar testes de integração cobrindo o pipeline completo (ingestão → resposta). |
| RF-TEST-06 | Implementar testes de regressão que rodem o golden set periodicamente (ex.: a cada mudança relevante de configuração) e alertem sobre degradação de qualidade. |

---

## 5. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-TEST-01 | O golden set deve ser representativo do uso real, não um conjunto artificial/genérico — construído a partir do corpus real da organização. |
| RNF-TEST-02 | Testes unitários/integração devem rodar rapidamente (sem depender de GPU/LM Studio real) usando fakes/mocks, permitindo execução frequente em CI. |
| RNF-TEST-03 | Testes de regressão contra o golden set real (com LM Studio/embeddings reais) podem ser mais lentos e rodar com menor frequência (ex.: antes de releases), dado o custo computacional. |

---

## 6. Dependências

* Corpus real de documentos (amostra representativa) para construir o golden set.
* Todos os módulos do pipeline já especificados e implementados (para rodar testes de integração/regressão).

---

## 7. Critérios de Aceitação

* [ ] Golden set inicial (30-50 perguntas) está criado, versionado, e cobre os principais tipos de documento.
* [ ] Suíte de testes unitários cobre todos os módulos do pipeline com fakes/mocks (execução rápida).
* [ ] Testes de integração validam o pipeline completo ponta a ponta.
* [ ] Processo de teste de regressão contra o golden set está implementado e documentado.
* [ ] Perguntas negativas no golden set validam corretamente que a LLM admite não saber quando apropriado.

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Golden set de 30 perguntas (confirmado) pode ter significância estatística limitada para decisões de benchmark muito finas | Médio | Tratar resultados com cautela proporcional ao tamanho da amostra; expandir o golden set iterativamente se decisões (ex.: tamanho de chunk) ficarem muito próximas/ambíguas entre configurações |
| Golden set não representativo (ex.: só perguntas fáceis) pode mascarar problemas reais de recuperação | Médio | Incluir deliberadamente perguntas de diferentes níveis de dificuldade (resposta direta em um chunk vs. resposta que exige combinar informação de múltiplos chunks) na revisão humana |
| **Viés circular:** usar a mesma LLM (`qwen/qwen3.5-9b`) para gerar perguntas do golden set e depois ser avaliada com esse mesmo golden set pode inflar artificialmente métricas de qualidade | Médio | **Revisão humana obrigatória** (RF-TEST-01/02) é a mitigação principal — a LLM apenas propõe candidatos, nunca decide sozinha o que entra no conjunto de referência; revisor deve ativamente buscar perguntas desafiadoras, não apenas aprovar o que foi gerado |
| Manutenção do golden set pode ser negligenciada ao longo do tempo | Baixo | Versionamento explícito e revisão programada (ex.: a cada adição significativa de novos documentos ao corpus) |

---

## 9. Alternativas Avaliadas

*Não há alternativas arquiteturais relevantes — a criação de um golden set interno é um requisito explícito do projeto (`visao-geral.md`, seção "Testes"). A única decisão prática é o tamanho inicial (30-50 perguntas), escolhido como equilíbrio entre esforço de criação manual e significância estatística mínima.*

---

## 10. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Golden set inicial de **30 perguntas** (confirmado), geradas via LLM + revisão humana obrigatória | Equilibra esforço/velocidade de criação com mitigação do viés circular via supervisão humana | ✅ Confirmado |
| Testes unitários/integração com fakes/mocks (sem GPU real) para execução rápida em CI | Permite testes frequentes sem custo computacional alto | Proposto |
| Testes de regressão contra golden set real rodam com menor frequência (pré-release) | Equilibra custo computacional com necessidade de validação de qualidade | Proposto |

---

## 11. Estratégia de Testes (Meta)

Esta própria spec define a estratégia de testes do projeto; não há uma "estratégia de testes para a estratégia de testes" além de: revisar periodicamente a cobertura do golden set frente a mudanças no corpus real, e garantir que a suíte de testes unitários/integração continue passando a cada mudança de código (CI).

---

## 12. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Decisões confirmadas pelo usuário | Processo semi-automatizado (LLM + revisão humana obrigatória); meta de 30 perguntas para a v1 do golden set |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `benchmark.md` — última especificação da lista |

---

**Próximo passo:** avançar para `benchmark.md`, a especificação final, detalhando o módulo de benchmark automatizado e as métricas mensuráveis de qualidade.
