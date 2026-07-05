# DocuRAG — Plataforma RAG Monolítica-Modular

O **DocuRAG** é uma plataforma corporativa completa de **Retrieval-Augmented Generation (RAG)** focada em processamento e indexação assíncrona de documentos de múltiplos formatos com alta fidelidade de contexto e proteção rígida contra alucinações. 

A plataforma foi desenvolvida utilizando **Clean Architecture (Ports & Adapters)** sob o padrão de **Monólito Modular**, garantindo isolamento entre a lógica de negócios e as tecnologias de infraestrutura (bancos de dados, filas e provedores de IA).

---

## 🚀 Principais Funcionalidades

1. **Leitura Estruturada Multiformato (Parsing)**:
   * **PDF**: Extração nativa de texto e tabelas via `pdfplumber` com **fallback automático para OCR** utilizando Tesseract OCR (`pytesseract` com suporte a Português) para páginas escaneadas.
   * **Word (`.docx`)**: Extração de parágrafos estruturados, headings e tabelas.
   * **Excel (`.xlsx`)**: Conversão automática de abas e tabelas em representações Markdown estruturadas para alimentação otimizada da LLM.
   * **TXT & CSV**: Leitura nativa rápida com detecção automática de encoding (`charset-normalizer`).

2. **Limpeza e Enriquecimento Semântico**:
   * **Normalização**: Limpeza por expressão regular de ruídos de Unicode, quebras de linhas órfãs e resíduos de OCR.
   * **Enriquecimento Taxonômico**: Extração automática de palavras-chave e categorias utilizando o algoritmo YAKE (Yet Another Keyword Extractor) anexadas aos metadados dos chunks.

3. **Divisão Inteligente (Chunking)**:
   * Chunker híbrido combinando divisões estruturais de seções, chunking semântico baseado na distância de cosseno entre vetores de sentenças adjacentes e grid adaptativo para tabelas (duplicando cabeçalhos em partes fragmentadas).

4. **Busca Híbrida & Re-ranqueamento (RAG)**:
   * **Busca Lexical (BM25)** + **Busca Vetorial (Cosine Similarity)** combinadas através de **Reciprocal Rank Fusion (RRF)**.
   * Filtro de deduplicação semântica baseado na similaridade de Jaccard no nível das palavras (limiar de `0.7`).
   * Reordenação final dos resultados utilizando um modelo local de **Cross-Encoder** (`BAAI/bge-reranker-base`).
   * Limitação rígida de orçamento de contexto de 5.000 tokens calculados no tokenizer da LLM.

5. **Infraestrutura Concorrente & Resiliente**:
   * **Processamento Assíncrono**: Ingestão enfileirada no Redis gerenciada por workers do RQ (Redis Queue) em segundo plano.
   * **Persistência Vetorial**: Banco Qdrant embutido local. Acesso concorrente otimizado (abertura/fechamento dinâmico de conexões para evitar travamento de SQLite em concorrência API vs. Worker).
   * **Indexação Transacional**: Estratégia de inserção dos novos chunks primeiro, seguida de exclusão condicional baseada em carimbo de data/hora (`version_timestamp`), anulando janelas de inconsistência ou dados órfãos.

6. **Avaliação de Qualidade & Benchmark**:
   * Pipeline de benchmark automatizado consumindo um dataset versionado de **30 perguntas de referência** (factuais e negativas). Calcula MRR, nDCG, Hit Rate, latências do sistema, índice de Grounding (presença de entidades da resposta no contexto) e taxa de admissão de ignorância de forma contínua em `data/benchmark_report.md`.

7. **Painel Front-End Integrado**:
   * Interface gráfica web SPA no estilo *Sleek Dark Cyberpunk*, com upload intuitivo, polling do status de ingestão, chat RAG interativo com destaque visual de citações e disparador de benchmarks de performance.

---

## 📁 Estrutura do Projeto

```text
docurag/
├── data/                       # Diretório persistente (Uploads, SQLite DB e Qdrant)
│   ├── uploads/                # Arquivos salvos físicamente
│   ├── qdrant/                 # Banco vetorial local do Qdrant
│   ├── docurag.db              # Banco SQLite de status de ingestão
│   └── benchmark_report.md     # Relatório consolidado de benchmarks
├── specs/                      # 18 especificações técnicas da plataforma (SDD)
├── src/                        # Código Fonte (Clean Architecture)
│   ├── domain/                 # Entidades e Portas (Interfaces)
│   ├── application/            # Casos de Uso (Negócio)
│   ├── infrastructure/         # Adaptadores (Implementações de Infra)
│   │   ├── adapters/           # Parsers, Chunker, Embeddings, Vector Store, RAG, etc.
│   │   ├── database/           # Repository SQLite
│   │   └── queue/              # RQ tasks e queue manager
│   └── presentation/           # FastAPI Endpoints e arquivos estáticos do Painel
│       └── static/             # Front-end (HTML, CSS e JS)
├── tests/                      # Suíte de Testes (pytest) e Golden Set
├── Dockerfile                  # Definição do contêiner da aplicação
├── docker-compose.yml          # Orquestração da API, Worker e Redis
├── run.py                      # Script de inicialização da API
├── worker.py                   # Script de inicialização do Worker
└── requirements.txt            # Dependências Python
```

---

## ⚙️ Configuração do Ambiente (.env)

A plataforma utiliza um arquivo `.env` na raiz do projeto para configurar variáveis de comportamento de API, modelos de inteligência artificial, filas e limiares de processamento. 

Para configurar o seu ambiente, crie um arquivo chamado **`.env`** na raiz do projeto e preencha-o seguindo o modelo abaixo:

```ini
# --- API Settings ---
API_KEY=docurag_secret_api_key_v1   # Chave de segurança exigida nas requisições HTTP (X-API-Key)
LOG_LEVEL=INFO                      # Nível de granularidade de logs (DEBUG, INFO, WARNING, ERROR)
PORT=8000                           # Porta exposta para acesso externo à API
HOST=0.0.0.0                        # Endereço de vinculação de rede do servidor

# --- External Services ---
REDIS_URL=redis://localhost:6379/0  # URL de conexão ao broker Redis (em produção o compose sobrescreve para redis://redis:6379/0)

# --- LLM Provider Settings (LM Studio) ---
LM_STUDIO_URL=http://localhost:1234/v1               # Endpoint compatível com OpenAI da LLM executando no host
LLM_MODEL_NAME=google/gemma-3-4b                     # Nome do modelo a ser consultado no LM Studio

# --- Local AI Models (Embeddings & Rerank) ---
EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-base   # Modelo de embedding local
RERANK_MODEL_NAME=BAAI/bge-reranker-base             # Modelo Cross-Encoder local de reordenação

# --- Processing configs (Chunking) ---
CHUNK_SIZE_TARGET=512   # Tamanho alvo em tokens para divisão semântica de chunks
CHUNK_OVERLAP=64        # Quantidade de tokens sobrepostos entre chunks adjacentes

# --- HuggingFace Cache Directory (Portabilidade) ---
# Mapeia a pasta do seu host para evitar o download repetido de 1.5GB de pesos de modelo no contêiner
HF_CACHE_DIR=C:/Users/seu_usuario/.cache/huggingface
```

---

## 🛠️ Instalação e Execução (Docker Compose)

> [!IMPORTANT]
> **Aceleração e Cache de Modelos HuggingFace**: 
> A configuração do Docker monta o cache do HuggingFace no contêiner. Por padrão, é criado o diretório local `.hf_cache` na raiz do projeto para persistir os pesos dos modelos.
> Se desejar reutilizar o cache global da sua máquina para evitar novos downloads, defina a variável de ambiente `HF_CACHE_DIR` antes de iniciar os contêineres (ex: no Windows PowerShell: `$env:HF_CACHE_DIR="C:/Users/seu_usuario/.cache/huggingface"` ou criando um arquivo `.env` com `HF_CACHE_DIR=C:/Users/seu_usuario/.cache/huggingface`).

### 1. Iniciar toda a pilha RAG:
Na pasta raiz do projeto, execute:
```bash
docker compose up -d --build
```
Isto fará o build das imagens baixando o Tesseract OCR (Português), poppler e instalará as dependências Python. Os serviços criados serão:
* **`docurag_redis`**: Porta `6379`.
* **`docurag_api`**: Porta `8000`.
* **`docurag_worker`**: Executando as tarefas de background.

### 2. Acessar o Dashboard Web:
Abra seu navegador e acesse:
👉 **[http://localhost:8000/](http://localhost:8000/)** (será redirecionado para `/dashboard/`).

---

## 🔌 API REST Endpoints

Todas as rotas de escrita/consulta exigem autenticação via Header `X-API-Key: docurag_secret_api_key_v1`.

| Rota | Método | Descrição |
| :--- | :--- | :--- |
| `/documents/ingest` | `POST` | Faz o upload de um arquivo de documento e enfileira para processamento. |
| `/documents/{id}` | `GET` | Consulta o status de ingestão de um documento (`enfileirado`, `processando`, `concluido`, `erro`). |
| `/documents/{id}` | `DELETE` | Apaga permanentemente o documento do disco e expurga seus chunks do banco vetorial. |
| `/query` | `POST` | Realiza a consulta RAG com busca lexical/vetorial fusionada, re-ranking e resposta da LLM. |
| `/stats` | `GET` | Recupera estatísticas da fila do Redis e volume de documentos ativos. |
| `/health` | `GET` | Endpoint público para checagem de saúde da API, SQLite, Qdrant e Redis. |
| `/benchmark/run` | `POST` | Dispara a avaliação contra o Golden Set de 30 questões salvando no histórico. |
| `/benchmark/results` | `GET` | Recupera a lista histórica de rodadas de benchmark executadas. |

---

## 🧪 Rodando os Testes Automatizados

O DocuRAG possui uma suíte contendo **29 testes unitários e de integração** para garantir a estabilidade do sistema contra regressões.

Para rodar os testes localmente no host:
```bash
pip install -r requirements.txt
python -m pytest
```
