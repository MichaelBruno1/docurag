# Especificação: Normalização de Texto

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `parsing.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Limpar e normalizar o texto extraído pelo estágio de parsing, removendo ruído (artefatos de extração, OCR, encoding) e padronizando o texto para que os estágios seguintes (enriquecimento, chunking, embeddings) operem sobre conteúdo consistente e de alta qualidade — especialmente crítico dado que o texto de origem inclui saída de **OCR**, que tende a introduzir ruído específico.

---

## 2. Escopo

Cobre a limpeza e padronização do campo `content` de cada seção do `ParsedDocument` (definido em `parsing.md`). Não cobre geração de metadados (`enriquecimento.md`) nem divisão em chunks (`chunking.md`).

---

## 3. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF-NORM-01 | Remover caracteres de controle inválidos e normalizar encoding para UTF-8 em todo o texto. |
| RF-NORM-02 | Corrigir/normalizar espaçamento excessivo (múltiplos espaços, quebras de linha redundantes) sem destruir a separação lógica entre parágrafos. |
| RF-NORM-03 | Remover artefatos comuns de extração de PDF: hifenização quebrada no fim de linha (ex.: "infor-\nmação" → "informação"), cabeçalhos/rodapés repetidos em todas as páginas, numeração de página solta no meio do texto. |
| RF-NORM-04 | **Tratamento específico para saída de OCR (engine confirmado: Tesseract):** aplicar correções para erros comuns e conhecidos da saída do Tesseract (ex.: caracteres confundidos como "l"/"1"/"I"/"0"/"O", espaços espúrios dentro de palavras, ruído de baixa confiança em regiões de imagem degradada), sem exigir correção ortográfica completa baseada em IA nesta etapa. |
| RF-NORM-05 | Preservar estrutura de tabelas e listas (não deve "achatar" uma tabela em texto corrido sem separadores). |
| RF-NORM-06 | **Confirmado:** normalização de datas/números **não será feita** nesta etapa — o texto permanece como extraído, confiando na capacidade interpretativa da LLM (4B–9B) para lidar com variações de formato durante a geração da resposta. |
| RF-NORM-07 | Detectar e marcar (não necessariamente remover) trechos de baixíssima confiança de OCR, para que `enriquecimento.md`/`chunking.md` possam decidir como tratá-los (ex.: excluir de chunks finais ou marcar com aviso de baixa confiabilidade). |

---

## 4. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-NORM-01 | A normalização não deve ser tão agressiva a ponto de remover informação semanticamente relevante (equilíbrio entre limpeza e preservação de conteúdo — RNF-02 da visão geral). |
| RNF-NORM-02 | O processo deve ser determinístico: o mesmo texto de entrada deve sempre produzir a mesma saída normalizada (facilita testes de regressão). |
| RNF-NORM-03 | Etapas de normalização devem ser configuráveis/compostas (pipeline de transformações), permitindo habilitar/desabilitar regras específicas (ex.: regras de OCR só se aplicam a texto originado de OCR). |

---

## 5. Dependências

* `ParsedDocument` (saída de `parsing.md`), incluindo indicação de qual seção/trecho veio de OCR (necessário para RF-NORM-04 e RF-NORM-07).
* **Engine de OCR confirmado: Tesseract** (roda em CPU) — isso resolve favoravelmente o risco de contenção de GPU levantado em `parsing.md`, já que o Tesseract não compete com LM Studio/embeddings pela GPU compartilhada.
* Nenhuma dependência de modelo de IA nesta etapa (a normalização é baseada em regras determinísticas, não em LLM) — mantém a etapa rápida e barata computacionalmente, preservando GPU para embeddings/LLM.

---

## 6. Critérios de Aceitação

* [ ] Texto normalizado não contém caracteres de controle inválidos ou problemas de encoding.
* [ ] Hifenização quebrada de PDF é corrigida nos casos comuns testados.
* [ ] Cabeçalhos/rodapés repetidos identificados e removidos em um documento de teste com múltiplas páginas.
* [ ] Erros comuns de OCR (confusão de caracteres, espaços espúrios) são corrigidos em um conjunto de teste com texto de OCR conhecido.
* [ ] Tabelas e listas mantêm sua estrutura reconhecível após a normalização.
* [ ] Trechos de baixa confiança de OCR são marcados corretamente na saída.
* [ ] O processo é determinístico (mesmo input sempre gera mesmo output em execuções repetidas).

---

## 7. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Normalização agressiva demais pode remover conteúdo relevante (ex.: um cabeçalho repetido pode às vezes ser conteúdo legítimo) | Médio | Regras conservadoras + validação por benchmark de qualidade de contexto final |
| Correção de erros de OCR baseada em regras fixas pode não cobrir todos os padrões de erro do **Tesseract** | Médio | Calibrar regras com base em padrões de erro conhecidos e documentados do Tesseract; medir taxa de erro residual via benchmark, ajustando regras iterativamente |
| Normalização de datas/números pode gerar ambiguidade (ex.: 01/02/2026 é 1º de fevereiro ou 2 de janeiro?) | Baixo-Médio (mitigado) | **Confirmado: não normalizar datas/números nesta etapa**; risco de má interpretação transferido para a LLM durante a geração de resposta — aceitável dado o porte do modelo (4B–9B) e o corpus majoritariamente em português (formato DD/MM/AAAA consistente) |

---

## 8. Alternativas Avaliadas

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| Normalização baseada em regras determinísticas (regex, heurísticas) | Rápida, barata, determinística, sem uso de GPU | Cobertura limitada a padrões conhecidos | **Proposto para v1** |
| Normalização assistida por LLM (usar o próprio modelo local para "limpar" o texto) | Potencialmente mais robusta a erros variados de OCR | Custo computacional alto (compete por GPU já compartilhada), não determinística, risco de alucinação/alteração de conteúdo | Rejeitado para v1 — contraria RNF-NORM-02 (determinismo) e onera a GPU compartilhada |

---

## 9. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Normalização 100% baseada em regras determinísticas, sem uso de LLM/GPU | Preserva determinismo, testabilidade e não sobrecarrega GPU já compartilhada (LM Studio + embeddings + OCR) | Proposto |
| Pipeline de transformações configurável/composável | Permite habilitar regras específicas (ex.: apenas para texto de OCR) sem acoplar toda a lógica em uma função monolítica | Proposto |

---

## 10. Estratégia de Testes

* **Unitários:** cada regra de normalização testada isoladamente com casos conhecidos (hifenização, espaçamento, encoding, erros de OCR).
* **Regressão:** conjunto de documentos de referência (incluindo saída real de OCR) com normalização esperada documentada.
* **Integração:** parsing → normalização, validando que a estrutura (`ParsedDocument`) permanece íntegra após a limpeza.
* **Qualidade:** comparação indireta via benchmark de recuperação — medir se a normalização melhora ou piora métricas de qualidade de contexto (parte do módulo `benchmark.md`).

---

## 11. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Decisões confirmadas pelo usuário | Datas/números não são normalizados (confia-se na LLM); engine de OCR confirmado como Tesseract |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `enriquecimento.md` |

**⚠️ Nota positiva para a arquitetura:** a escolha do Tesseract (CPU-based) resolve favoravelmente o risco de contenção de GPU identificado em `parsing.md`, já que não compete com LM Studio/embeddings pela GPU compartilhada confirmada em `arquitetura.md`.

---

**Próximo passo:** avançar para `enriquecimento.md`, detalhando a geração de metadados ricos por chunk.
