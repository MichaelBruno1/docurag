# Especificação: Parsing (Extração de Texto e Estrutura)

**Status:** ✅ Aprovado
**Versão:** 1.0
**Depende de:** `visao-geral.md` (v1.0), `arquitetura.md` (v1.0), `ingestao.md` (v1.0)
**Data:** 2026-07-04

---

## 1. Objetivo

Extrair texto e estrutura semântica (títulos, seções, tabelas, hierarquia) de cada formato suportado, produzindo uma representação intermediária uniforme que os estágios seguintes (`normalizacao.md`, `enriquecimento.md`, `chunking.md`) possam consumir independentemente do formato original.

---

## 2. Escopo

Cobre a implementação da porta `DocumentParser` (definida em `arquitetura.md`) para cada formato: PDF, DOCX, XLSX, CSV, TXT, Markdown. Não cobre limpeza/normalização de texto (`normalizacao.md`) nem geração de metadados semânticos além da estrutura básica extraída (`enriquecimento.md`).

---

## 3. Representação Intermediária Uniforme

Independente do formato de origem, o parser deve produzir uma estrutura comum, por exemplo:

```
ParsedDocument {
  document_id: string
  source_format: enum
  title: string | null
  sections: [
    {
      heading: string | null
      level: int            // hierarquia (h1, h2, h3...)
      content: string
      page_number: int | null
      tables: [ Table ] | []
    }
  ]
  raw_metadata: { author, created_at, ... }  // quando disponível no arquivo original
}
```

Essa uniformidade é o que permite que `chunking.md` e `enriquecimento.md` operem sem conhecer o formato original.

---

## 4. Requisitos Funcionais por Formato

| ID | Requisito |
|----|-----------|
| RF-PARSE-01 | **PDF:** extrair texto preservando ordem de leitura, títulos/hierarquia quando detectáveis (via fontes/tamanhos ou bookmarks), número de página por trecho, e tabelas quando estruturalmente identificáveis. |
| RF-PARSE-02 | **DOCX:** extrair texto preservando estilos de título (Heading 1/2/3...), parágrafos, tabelas e listas, mantendo hierarquia de seções. |
| RF-PARSE-03 | **XLSX:** extrair dados por planilha/aba, preservando cabeçalhos de coluna e estrutura tabular (não converter cegamente para texto corrido). |
| RF-PARSE-04 | **CSV:** extrair dados preservando cabeçalho e tipos de coluna quando inferíveis. |
| RF-PARSE-05 | **TXT:** extrair texto bruto; detectar encoding automaticamente (UTF-8, Latin-1, etc.). |
| RF-PARSE-06 | **Markdown:** extrair texto preservando hierarquia de headings, listas, tabelas e blocos de código como estrutura, não como texto corrido indiferenciado. |
| RF-PARSE-07 | Todo parser deve popular a estrutura intermediária uniforme (`ParsedDocument`), independentemente do formato de origem. |
| RF-PARSE-08 | Falha de parsing em um documento não deve interromper o processamento de outros documentos (isolamento de falhas, RNF-ING-03 da spec de ingestão). |
| RF-PARSE-09 | Documentos com conteúdo não textual apenas (ex.: PDF puramente escaneado sem camada de texto) devem ser identificados automaticamente e encaminhados para **OCR** (confirmado como parte do escopo da v1), em vez de apenas reportar "sem texto extraível". |
| RF-PARSE-10 | **Confirmado:** implementar suporte a **OCR** para PDFs escaneados (e páginas mistas — parcialmente escaneadas), produzindo texto extraído que alimenta a mesma estrutura `ParsedDocument` dos demais formatos. |
| RF-PARSE-11 | **Confirmado (XLSX):** todas as abas de um arquivo XLSX compõem um **único documento lógico** — cada aba é representada como uma seção/tabela dentro do mesmo `ParsedDocument`, preservando o nome da aba como identificador de seção. |

---

## 5. Requisitos Não Funcionais

| ID | Requisito |
|----|-----------|
| RNF-PARSE-01 | **Extensibilidade crítica:** o usuário confirmou que **novos formatos serão adicionados no futuro** (ex.: HTML, e-mails, imagens com texto). A interface `DocumentParser` deve ser projetada como um registro plugável (ex.: `ParserRegistry` mapeando MIME-type/extensão → implementação), permitindo adicionar um novo parser sem alterar código de `ingestao.md` ou dos estágios seguintes (RF-02 da visão geral). |
| RNF-PARSE-02 | Preservar o máximo de estrutura semântica possível — este é um requisito crítico dado o uso por LLMs pequenas (4B–9B), que se beneficiam de contexto bem organizado (RNF-04 da visão geral). |
| RNF-PARSE-03 | Tempo de parsing deve ser mensurado e reportado (contribui para métricas de "tempo médio de indexação" do módulo de benchmark). |

---

## 6. Dependências

* Bibliotecas de extração por formato — a avaliar tecnicamente (ex.: PDF: `pdfplumber`/`PyMuPDF`; DOCX: `python-docx`/`mammoth`; XLSX: `openpyxl`; Markdown: parser AST como `markdown-it` ou similar). **Decisão técnica de biblioteca não é objeto desta spec** — pode ser detalhada em ADR específico durante a implementação, desde que respeite a interface `DocumentParser`.
* Estrutura intermediária uniforme (`ParsedDocument`) deve ser acordada com `normalizacao.md`, `enriquecimento.md` e `chunking.md`.

---

## 7. Critérios de Aceitação

* [ ] Cada um dos 6 formatos suportados é convertido corretamente para a estrutura `ParsedDocument`.
* [ ] Hierarquia de títulos/seções é preservada quando presente no documento original.
* [ ] Tabelas (DOCX, XLSX, PDF quando aplicável) são extraídas como estrutura tabular, não como texto corrido sem separação de colunas.
* [ ] Documentos sem texto extraível (ex.: PDF escaneado sem OCR) são sinalizados corretamente, sem falha silenciosa.
* [ ] Falha em um documento específico não interrompe o processamento em lote de outros documentos.
* [ ] Tempo de parsing por documento é registrado e reportável.

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| PDFs escaneados (imagem) não têm texto extraível diretamente | Alto | **Confirmado: OCR está no escopo da v1.** Detectar páginas sem camada de texto e aplicar OCR automaticamente; qualidade do OCR deve ser medida via benchmark (taxa de erro de caracteres) |
| Extração de tabelas complexas (mescladas, aninhadas) em PDF é tecnicamente difícil e sujeita a erros | Médio | Aceitar qualidade "melhor esforço" para tabelas complexas em PDF; medir via benchmark e ajustar biblioteca se necessário |
| Perda de hierarquia semântica em DOCX sem uso consistente de estilos de título pelo autor original | Médio | Fallback heurístico (ex.: tamanho de fonte, negrito) quando estilos não estão presentes; documentar limitação |
| XLSX com múltiplas abas e estruturas heterogêneas pode gerar chunks pouco úteis se tratado ingenuamente | Médio | Tratar cada aba como uma seção própria dentro do documento lógico único, com cabeçalho preservado, encaminhado como estrutura tabular para o `enriquecimento.md`/`chunking.md` |
| OCR pode ser lento e/ou competir por GPU já compartilhada entre LM Studio e embeddings (`arquitetura.md`, seção 6) | Baixo (mitigado) | **Confirmado em `normalizacao.md`: engine escolhido é o Tesseract (CPU-based)** — não compete pela GPU compartilhada, resolvendo favoravelmente este risco |

---

## 9. Alternativas Avaliadas

*Comparação técnica de bibliotecas específicas por formato será registrada em ADRs próprios durante a implementação (ex.: `ADR-003-biblioteca-pdf.md`), com benchmark de qualidade de extração e velocidade, conforme exigido pelos princípios do projeto (nunca escolher por popularidade).*

---

## 10. Decisões Arquiteturais (ADR-resumo)

| Decisão | Justificativa | Status |
|---------|---------------|--------|
| Estrutura intermediária uniforme (`ParsedDocument`) para todos os formatos | Desacopla estágios seguintes do formato de origem (RNF-PARSE-01) | Proposto |
| Documentos sem texto extraível são encaminhados para OCR automaticamente, não apenas sinalizados | Requisito confirmado; documentação corporativa inclui digitalizações | ✅ Confirmado |
| `ParserRegistry` plugável (mapa extensão/MIME → parser) em vez de lógica condicional fixa | Usuário confirmou expansão futura de formatos; evita reescrever roteamento a cada novo formato | ✅ Confirmado |
| Todas as abas de um XLSX formam um único documento lógico | Confirmado pelo usuário; simplifica granularidade de gestão de documentos | ✅ Confirmado |

---

## 11. Estratégia de Testes

* **Unitários:** um parser por formato, testado com arquivos de exemplo representativos (incluindo casos-limite: tabelas complexas, múltiplos níveis de heading, arquivos vazios).
* **Integração:** pipeline ingestão → parsing → saída em `ParsedDocument`, validando estrutura de saída.
* **Regressão:** conjunto fixo de documentos de referência por formato, comparando saída estruturada esperada.
* **Desempenho:** tempo de parsing por tamanho/complexidade de documento.

---

## 12. Histórico de Aprovação

| Data | Ação | Observações |
|------|------|-------------|
| 2026-07-04 | Rascunho criado (v0.1) | Pendências levantadas |
| 2026-07-04 | Decisões confirmadas pelo usuário | OCR no escopo da v1; XLSX = documento lógico único (todas as abas); extensibilidade para formatos futuros é requisito explícito |
| 2026-07-04 | **Spec aprovada (v1.0)** | Liberado avanço para `normalizacao.md` |

**⚠️ Nota para revisão futura:**
* ✅ Engine de OCR **confirmado como Tesseract** (ver `normalizacao.md`) — CPU-based, sem contenção de GPU.
* O `ParserRegistry` deve ser desenhado desde já pensando em formatos futuros como HTML e e-mails (.eml), mesmo que não implementados nesta fase.

---

**Próximo passo:** avançar para `normalizacao.md`, detalhando limpeza e normalização do texto extraído.
