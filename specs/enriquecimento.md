# Especificação: Enriquecimento de Metadados

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `normalizacao.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Gerar metadados ricos para cada seção/trecho do documento normalizado, permitindo filtros precisos na recuperação (`recuperacao.md`), rastreabilidade completa (RF-10 da visão geral) e citação clara na resposta final. Metadados de qualidade são um multiplicador de precisão de recuperação, especialmente importante para compensar as limitações de modelos de 4B–9B parâmetros.

---

## 2. Escopo

Cobre a geração de metadados estruturados por seção do documento normalizado, antes da divisão em chunks (`chunking.md`). Alguns metadados (ex.: relacionamento entre chunks) só podem ser finalizados após o chunking — este documento define quais metadados são gerados nesta etapa vs. finalizados posteriormente.

---

## 3. Metadados por Chunk (Especificação Detalhada)

| Metadado | Origem | Momento de geração |
|----------|--------|---------------------|
| `documento_id` | Ingestão (UUID do documento) | Nesta etapa (herdado) |
| `nome_arquivo` | Ingestão | Nesta etapa (herdado) |
| `capitulo` / `secao` / `subtitulo` | Estrutura do `ParsedDocument` (heading/hierarquia) | Nesta etapa |
| `pagina` | `ParsedDocument` (quando aplicável — PDF) | Nesta etapa |
| `categoria` | Classificação automática (ex.: com base em palavras-chave/heurística simples, dado que não há requisito de compliance/classificação formal — `visao-geral.md` seção 2.2) | Nesta etapa, com abordagem simples (ver pendência) |
| `autor` | Metadados nativos do arquivo (`raw_metadata` do `ParsedDocument`), quando disponível | Nesta etapa |
| `data` | Metadados nativos do arquivo ou data de upload como fallback | Nesta etapa |
| `idioma` | Fixo: `pt-BR` (confirmado corpus 100% português em `visao-geral.md`) | Nesta etapa (valor constante, sem necessidade de detecção automática) |
| `palavras_chave` | Extração automática (ex.: TF-IDF, RAKE, ou YAKE — técnica simples e leve, sem uso de LLM/GPU) | Nesta etapa |
| `chunk_id` | Gerado durante o chunking | `chunking.md` |
| `relacionamento_com_outros_chunks` (ex.: chunk anterior/próximo, chunk-pai de seção) | Depende da divisão final em chunks | `chunking.md`, referenciando estrutura definida aqui |
| `origem_ocr` (booleano) + `confianca_ocr` (quando aplicável) | Propagado de `parsing.md`/`normalizacao.md` | Nesta etapa (herdado) |

---

### 3.1 Taxonomia Inicial de Categorias (Proposta)

Dado que não há taxonomia pré-definida nem estrutura de pastas a aproveitar (confirmado pelo usuário), propõe-se a seguinte taxonomia inicial, comum a ambientes de documentação técnica/corporativa, detectada via palavras-chave no título e nas primeiras seções do documento:

| Categoria | Sinais heurísticos (exemplos de palavras-chave/título) |
|-----------|----------------------------------------------------------|
| `Manual` | "manual", "guia do usuário", "instruções de uso" |
| `Política` | "política", "diretriz", "norma interna" |
| `Procedimento` | "procedimento", "processo", "POP", "passo a passo" |
| `Especificação Técnica` | "especificação", "spec", "requisitos técnicos", "arquitetura" |
| `Relatório` | "relatório", "análise", "resultado", "levantamento" |
| `Outro` | Nenhum sinal forte identificado (categoria padrão/fallback) |

**Regras de aplicação:**
* A detecção é feita por correspondência de termos (case-insensitive, com suporte a variações simples) no título do documento e, secundariamente, nas primeiras ~200 palavras do conteúdo.
* Se nenhuma categoria for identificada com confiança suficiente, o documento recebe `Outro` — nunca fica com o campo vazio/nulo (RNF-ENR-02, consistência).
* Esta taxonomia é um ponto de partida deliberadamente simples; deve ser revisada com base em uso real e, se necessário, expandida ou ajustada — o esquema versionado (RNF-ENR-03) permite essa evolução sem quebrar documentos já indexados.
* Um documento pode, no futuro, ter múltiplas categorias (multi-label) se a heurística simples se mostrar insuficiente — não implementado na v1 por simplicidade.

| ID | Requisito |
|----|-----------|
| RF-ENR-01 | Gerar metadados estruturais (capítulo, seção, subtítulo, página) a partir da hierarquia do `ParsedDocument`. |
| RF-ENR-02 | Extrair palavras-chave automaticamente por seção, usando técnica leve (sem LLM/GPU), gerando uma lista de termos representativos. |
| RF-ENR-03 | Propagar metadados nativos do arquivo (autor, data de criação) quando disponíveis; usar fallback (data de upload) quando ausentes. |
| RF-ENR-04 | Fixar `idioma = pt-BR` para todos os documentos (dado o corpus confirmado como exclusivamente em português). |
| RF-ENR-05 | Propagar indicadores de origem/confiança de OCR (`origem_ocr`, `confianca_ocr`) do estágio de normalização. |
| RF-ENR-06 | **Confirmado:** não há taxonomia pré-definida pela organização nem estrutura de pastas/nomenclatura a aproveitar. Adota-se uma **taxonomia inicial simples e heurística**, proposta abaixo (seção 3.1), baseada em palavras-chave detectadas no título/conteúdo do documento. Categoria pode ser recalculada/refinada no futuro sem quebrar dados já indexados (RNF-ENR-03). |
| RF-ENR-07 | Todo metadado gerado deve ser armazenado de forma que sobreviva ao chunking (ou seja, propagável a cada chunk resultante de uma seção). |

---

## 5. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-ENR-01 | Extração de palavras-chave e categorização não devem depender de GPU/LLM — mantém a etapa rápida e evita mais contenção na GPU compartilhada (LM Studio + embeddings). |
| RNF-ENR-02 | Metadados devem ser consistentes e determinísticos entre execuções (facilita testes e comparação em benchmark). |
| RNF-ENR-03 | O esquema de metadados deve ser extensível — permitir adicionar novos campos de metadado no futuro sem quebrar documentos já indexados (versionamento de esquema). |

---

## 6. Dependências

* `ParsedDocument` normalizado (saída de `normalizacao.md`).
* Biblioteca de extração de palavras-chave leve (ex.: YAKE, RAKE, ou TF-IDF simples) — decisão técnica específica pode ser um ADR próprio.
* Definição de taxonomia de `categoria`, se houver uma pré-definida pela organização (ver pendência).

---

## 7. Critérios de Aceitação

* [ ] Cada chunk resultante do pipeline carrega metadados completos: documento, capítulo/seção, página (quando aplicável), categoria, autor, data, idioma, palavras-chave, ID único.
* [ ] Metadados de OCR (origem e confiança) são corretamente propagados até o chunk final.
* [ ] Extração de palavras-chave roda sem uso de GPU e produz termos relevantes (validado manualmente em amostra de teste).
* [ ] O mesmo documento processado duas vezes produz os mesmos metadados (determinismo).
* [ ] Metadados são filtráveis no banco vetorial (validado em conjunto com `banco-vetorial.md`/`recuperacao.md`).

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Categorização automática simples (sem taxonomia formal da organização, confirmado) pode ser imprecisa ou gerar muitos documentos como "Outro" | Médio | Taxonomia inicial (seção 3.1) revisável; medir distribuição real de categorias após uso e ajustar palavras-chave/categorias conforme necessário |
| Extração de palavras-chave de baixa qualidade pode gerar filtros pouco úteis | Baixo-Médio | Validar qualidade via benchmark de recuperação; ajustar algoritmo se necessário |
| Metadados ausentes em arquivos sem informação nativa (ex.: TXT sem autor/data) | Baixo | Fallbacks definidos (data de upload, autor "desconhecido") evitam campos nulos problemáticos |

---

## 9. Alternativas Avaliadas

| Alternativa | Prós | Contras | Decisão |
|-------------|------|---------|---------|
| Extração de palavras-chave via LLM (prompt pedindo palavras-chave) | Potencialmente mais precisa semanticamente | Custo de GPU/tempo por chunk, não determinística | Rejeitado para v1 |
| Extração leve (YAKE/RAKE/TF-IDF) | Rápida, determinística, sem custo de GPU | Qualidade um pouco inferior a abordagens semânticas | **Proposto para v1** |
| Categorização via classificador de ML treinado | Mais precisa a longo prazo | Exige dados de treino e manutenção de modelo — não justificado para corpus pequeno | Rejeitado para v1 |
| Categorização heurística simples (palavras-chave/pasta de origem) | Simples, sem dependências extras | Menos precisa | **Proposto para v1** |

---

## 10. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Enriquecimento sem uso de LLM/GPU (extração leve de palavras-chave e categorização heurística) | Preserva GPU para embeddings/LLM; mantém determinismo (RNF-ENR-01, RNF-ENR-02) | Proposto |
| `idioma` fixado como `pt-BR` (constante, sem detecção automática) | Corpus confirmado 100% português em `visao-geral.md`; simplifica implementação | Proposto |
| Esquema de metadados versionado e extensível | Permite evolução futura sem quebrar dados já indexados (RNF-ENR-03) | Proposto |

---

## 11. Estratégia de Testes

* **Unitários:** geração de cada campo de metadado isoladamente (estrutural, palavras-chave, categoria, OCR).
* **Integração:** normalização → enriquecimento, validando que todos os campos obrigatórios são preenchidos (com fallback quando ausente na fonte).
* **Regressão:** conjunto de documentos de referência com metadados esperados documentados.
* **Qualidade:** impacto dos metadados na precisão de filtros de recuperação, medido via `benchmark.md`.

---

## 12. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Decisões confirmadas pelo usuário | Sem taxonomia formal nem estrutura de pastas; taxonomia heurística inicial proposta na seção 3.1 |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `chunking.md` |

**⚠️ Nota para revisão futura:** a taxonomia da seção 3.1 é um ponto de partida; recomenda-se revisá-la após observar a distribuição real de categorias no corpus corporativo, ajustando palavras-chave e possivelmente adicionando novas categorias.

---

**Próximo passo:** avançar para `chunking.md`, detalhando a estratégia de divisão em chunks (semântico, por seção, hierárquico, adaptativo).
