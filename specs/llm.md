# Especificação: Integração com a LLM (LM Studio)

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `construcao-contexto.md` (v1.0), `arquitetura.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Definir a integração da plataforma RAG com o **LM Studio**, servindo o modelo `qwen/qwen3.5-9b`, incluindo o design do prompt de sistema, o protocolo de comunicação (API compatível OpenAI), tratamento de erros/timeouts, e o contrato do `LLMProvider` (porta definida em `arquitetura.md`).

---

## 2. Escopo

Cobre a comunicação com o LM Studio e a construção do prompt final (sistema + contexto + pergunta) enviado ao modelo. Não cobre a seleção dos chunks em si (`construcao-contexto.md`) nem a lógica de recuperação (`recuperacao.md`).

---

## 3. Protocolo de Comunicação

O LM Studio expõe uma API compatível com o padrão OpenAI (`/v1/chat/completions` ou equivalente), conforme já confirmado em `arquitetura.md` (RNF-12). A integração deve:

* Enviar requisições HTTP para o endpoint local/rede privada do LM Studio.
* Usar o formato de mensagens `[{role: "system", content: ...}, {role: "user", content: ...}]`.
* Suportar parâmetros configuráveis: `temperature`, `max_tokens` (para a resposta), `top_p`, e outros relevantes para controle de determinismo/criatividade da resposta.
* Tratar timeouts e erros de conexão de forma resiliente (o LM Studio pode estar temporariamente indisponível, sobrecarregado, ou com o modelo ainda carregando).

---

## 4. Design do Prompt de Sistema

O prompt de sistema deve ser **enxuto** (orçamento de ~200-400 tokens, conforme `construcao-contexto.md`), contendo:

1. Instrução de papel: a LLM deve responder com base **exclusivamente** no contexto fornecido, evitando "alucinar" informação não presente nos chunks.
2. Instrução de citação: a resposta deve referenciar a origem da informação (documento/seção) quando possível, usando as referências mínimas incluídas em cada chunk (RF-CTX-04 de `construcao-contexto.md`).
3. Instrução de honestidade: se o contexto fornecido não contiver informação suficiente para responder, a LLM deve dizer isso explicitamente, em vez de inventar uma resposta.
4. Instrução de idioma: responder sempre em português (consistente com o corpus 100% em português confirmado em `visao-geral.md`).
5. Instrução de formato: manter respostas diretas e objetivas, adequadas ao caso de uso de documentação corporativa/técnica.

**Nota de engenharia:** dado que o modelo é pequeno (9B parâmetros), o prompt de sistema deve ser o mais direto e não ambíguo possível — modelos pequenos tendem a seguir instruções complexas ou muito longas com menos consistência que modelos maiores.

**Confirmado pelo usuário:** o texto exato do prompt de sistema não requer revisão prévia da equipe — a implementação tem liberdade para refiná-lo tecnicamente durante o desenvolvimento, respeitando os 5 princípios listados acima (grounding, citação, honestidade sobre limitações, idioma português, formato direto/objetivo). Recomenda-se, ainda assim, validar o prompt final empiricamente contra o golden set (`testes.md`) antes de considerá-lo definitivo.

---

## 5. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-LLM-01 | Implementar `LLMProvider` como cliente HTTP para a API do LM Studio, compatível com o padrão OpenAI de chat completions. |
| RF-LLM-02 | Construir a mensagem de sistema conforme o design da seção 4, mantendo-a dentro do orçamento de tokens estabelecido em `construcao-contexto.md`. |
| RF-LLM-03 | Enviar o contexto construído (`construcao-contexto.md`) e a pergunta do usuário como parte da mensagem, respeitando o limite total de 8k tokens. |
| RF-LLM-04 | Capturar e repassar a resposta da LLM, incluindo metadados relevantes (tokens usados, tempo de resposta) para observabilidade. |
| RF-LLM-05 | Implementar retry com backoff para falhas transitórias de comunicação com o LM Studio (ex.: timeout, conexão recusada). |
| RF-LLM-06 | Registrar, para cada resposta, o `trace_id`, os chunks usados (via `construcao-contexto.md`), e a resposta completa gerada — rastreabilidade total (RF-10 da visão geral). |
| RF-LLM-07 | Validar que a contagem de tokens da mensagem completa (sistema + contexto + pergunta) não excede o limite antes de enviar ao LM Studio, como camada final de segurança complementar a `construcao-contexto.md`. |

---

## 6. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-LLM-01 | O `LLMProvider` deve ser uma porta substituível — trocar o LM Studio por outro motor de inferência (ex.: outro servidor compatível OpenAI) não deve exigir alteração em `ContextBuilder` ou nos casos de uso da aplicação. |
| RNF-LLM-02 | Timeout configurável para chamadas ao LM Studio, evitando que uma consulta trave indefinidamente a API da plataforma. |
| RNF-LLM-03 | **Confirmado:** `temperature = 0.0` — máximo determinismo, priorizando consistência e factualidade sobre naturalidade estilística, adequado ao caso de uso corporativo/técnico. |

---

## 7. Dependências

* LM Studio operante na cloud privada, servindo `qwen/qwen3.5-9b` (confirmado em `embeddings.md`/`arquitetura.md`).
* Contexto construído por `construcao-contexto.md`.
* Biblioteca de tokenização compatível com o modelo Qwen, para validação final de tokens (RF-LLM-07), reaproveitando a mesma usada em `construcao-contexto.md`.

---

## 8. Critérios de Aceitação

* [ ] `LLMProvider` se comunica corretamente com o LM Studio via API compatível OpenAI.
* [ ] Prompt de sistema segue o design da seção 4 e permanece dentro do orçamento de tokens.
* [ ] Falhas transitórias de comunicação são tratadas com retry, sem quebrar a experiência do usuário.
* [ ] Toda resposta é rastreável (trace_id + chunks usados + resposta completa registrados).
* [ ] Nenhuma requisição excede o limite de 8k tokens (validação final antes do envio).
* [ ] Trocar o motor de inferência (hipoteticamente) não exigiria alterar `ContextBuilder` nem os casos de uso.

---

## 9. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| LM Studio indisponível ou lento (ex.: modelo ainda carregando após reinício) | Médio | Retry com backoff (RF-LLM-05) + timeout configurável (RNF-LLM-02) + mensagem de erro clara para o usuário |
| Prompt de sistema mal calibrado pode fazer o modelo pequeno ignorar instruções (ex.: citar fontes) | Médio | Testar e refinar o prompt de sistema com o golden set (`testes.md`), medindo aderência às instruções na prática |
| Modelo pequeno pode "alucinar" mesmo com instrução explícita de usar apenas o contexto fornecido | Alto | Complementar com avaliação de qualidade (`benchmark.md`) que meça especificamente fidelidade ao contexto fornecido (grounding), não apenas relevância dos chunks recuperados |
| `temperature = 0.0` pode, em casos raros, favorecer repetições/loops de texto em alguns modelos | Baixo | Monitorar esse comportamento no golden set; se ocorrer, considerar `repetition_penalty` ou parâmetros equivalentes disponíveis no LM Studio, mantendo determinismo geral |

---

## 10. Alternativas Avaliadas

*A escolha do motor de inferência (LM Studio) e do modelo (`qwen/qwen3.5-9b`) já foi confirmada pelo usuário em specs anteriores (`arquitetura.md`, `embeddings.md`) — não é reavaliada aqui. A única decisão técnica em aberto nesta spec é a calibração fina de parâmetros (`temperature`, prompt exato), a ser refinada por teste qualitativo/benchmark.*

---

## 11. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| `LLMProvider` como adaptador HTTP compatível OpenAI, isolado do resto da aplicação | Permite trocar o motor de inferência no futuro sem impacto arquitetural (RNF-LLM-01) | Proposto |
| Prompt de sistema enxuto e direto, com instruções explícitas de grounding e citação | Modelos pequenos (9B) respondem melhor a instruções simples e diretas | Proposto |
| `temperature = 0.0` confirmado | Máximo determinismo/factualidade, decisão explícita do usuário | ✅ Confirmado |

---

## 12. Estratégia de Testes

* **Unitários:** construção da mensagem de sistema, validação de contagem de tokens, tratamento de erros de comunicação.
* **Integração:** contexto → chamada ao LM Studio → resposta capturada corretamente.
* **Testes de resiliência:** simular indisponibilidade do LM Studio e validar retry/timeout.
* **Qualidade (crítico):** golden set usado para medir grounding (a resposta é fiel ao contexto fornecido?), aderência a instruções (cita fontes? admite quando não sabe?), como parte do `benchmark.md`.

---

## 13. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Decisões confirmadas pelo usuário | `temperature = 0.0`; liberdade total para refinar o prompt de sistema tecnicamente, sem revisão prévia obrigatória da equipe |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `api.md` |

---

**Próximo passo:** avançar para `api.md`, detalhando os endpoints da plataforma (upload, indexação, consulta, benchmark, estatísticas, monitoramento).
