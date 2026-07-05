# Especificação: Débitos Técnicos e Correções Prescritivas

**Status:** 📝 Proposto
**Versão:** 1.0
**Depende de:** `arquitetura.md`, `banco-vetorial.md`, `ingestao.md`, `api.md`
**Data:** 2026-07-05

---

## 1. Objetivo

Esta especificação identifica e registra os **débitos técnicos** presentes na implementação atual da plataforma DocuRAG que afetam a performance, resiliência sob carga e concorrência em produção. Ela define as propostas arquiteturais detalhadas para sua futura mitigação e correção.

---

## 2. Débito Técnico 1: Concorrência e Travamento de Escrita no SQLite (DT-01)

### 2.1 Descrição do Problema
O SQLite é utilizado pelo `SQLiteDocumentRepository` para armazenar metadados dos arquivos e os estados de processamento (`enfileirado`, `processando`, `concluido`, `erro`). Por padrão, a conexão SQLite opera em modo de transação tradicional (`DELETE` ou `TRUNCATE`), que bloqueia a base inteira para leituras durante uma operação de escrita. Sob alta carga (múltiplas requisições concorrentes de upload de arquivos), o SQLite pode gerar exceções de `sqlite3.OperationalError: database is locked`.

### 2.2 Prescrição de Correção
Configurar o banco SQLite para operar no modo **WAL (Write-Ahead Logging)** e estender o timeout de espera de transações. 

A alteração deve ser inserida na conexão do banco de dados em `src/infrastructure/database/repository.py`:
1. Habilitar a instrução PRAGMA de WAL:
   ```sql
   PRAGMA journal_mode=WAL;
   ```
2. Aumentar o timeout de conexão para 30 segundos:
   ```python
   sqlite3.connect(database_path, timeout=30.0)
   ```
*O modo WAL permite que múltiplos leitores acessem a base de dados em paralelo com um escritor ativo, eliminando colisões de consulta de status durante a escrita do Worker.*

---

## 3. Débito Técnico 2: Instanciação Dinâmica do Cliente Qdrant (DT-02)

### 3.1 Descrição do Problema
No modo embutido (*embedded*) do Qdrant (`QdrantClient(path="data/qdrant")`), a biblioteca fecha o arquivo de banco SQLite vetorial ao encerrar a instância. Para evitar que a API e o Worker concorram pelo arquivo (bloqueando a gravação de chunks), o adaptador `QdrantVectorStore` instancia o cliente sob demanda no início de cada operação (como busca ou escrita) e executa `client.close()` ao final de cada método. Embora isso previna colisões físicas de leitura/escrita, cria um overhead de I/O por requisição devido à reabertura constante de descritores de arquivo.

### 3.2 Prescrição de Correção
Quando o DocuRAG for migrado do Docker de desenvolvimento para um ambiente de produção usando um contêiner Qdrant centralizado:
1. Remover a criação e encerramento dinâmico do cliente em cada método do `QdrantVectorStore`.
2. Modificar o construtor do adaptador para receber o `QdrantClient` como uma dependência Singleton e mantê-lo ativo ao longo de todo o ciclo de vida (lifespan) da API e do Worker.
3. Configurar a URL de conexão externa no `src/config.py`:
   ```python
   # Utilizar porta REST/gRPC centralizada
   QDRANT_URL = "http://qdrant:6333"
   ```

---

## 4. Débito Técnico 3: Bloqueio de Thread Síncrona do Worker em OCR (DT-03)

### 4.1 Descrição do Problema
O parser de PDF (`PDFParser`) realiza chamadas síncronas ao Tesseract OCR quando o documento é escaneado ou não possui texto extraível. Como o Worker roda em uma única thread principal por processo do RQ, a conversão de múltiplas páginas de PDF em imagem e a posterior extração de texto via `pytesseract.image_to_string` bloqueiam a thread síncrona do Worker por longos períodos (por exemplo, 1 a 2 minutos para PDFs com mais de 30 páginas). Isso impede o recebimento de batimentos cardíacos (heartbeats) do Redis, podendo levar a tarefas marcadas incorretamente como mortas por timeout no RQ.

### 4.2 Prescrição de Correção
Implementar paralelismo no processamento de páginas de OCR:
1. Em vez de rodar o loop de páginas de forma síncrona e sequencial em `PDFParser._run_ocr`, separar o PDF em blocos de páginas.
2. Utilizar um pool de processos (`concurrent.futures.ProcessPoolExecutor`) para distribuir as imagens de páginas entre múltiplos núcleos de CPU do Worker.
3. Atualizar o status do progresso de páginas concluídas periodicamente na base SQLite para dar feedback em tempo real para a interface de monitoramento.

---

## 5. Débito Técnico 4: Validação de Fronteiras de Parâmetros na API (DT-04)

### 5.1 Descrição do Problema
O endpoint `/query` recebe parâmetros estruturados que são validados em tipo pelo Pydantic, mas não possuem restrições lógicas de limites inferiores e superiores (fronteiras). Um usuário mal-intencionado ou errôneo pode enviar um request com `top_k = 200` ou `top_k = -5`. Chamar a busca com valor negativo gerará erros na API do Qdrant/BM25, e valores excessivamente altos degradam a performance de re-ranking e estouram o limite de tokens do compilador de contexto desnecessariamente.

### 5.2 Prescrição de Correção
Adicionar restrições de limites de parâmetros na classe Pydantic `QueryRequest` em `src/presentation/api.py`:
```python
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(default=3, ge=1, le=15)
```
*Isso garante rejeição imediata na borda da API (HTTP 422 Unprocessable Entity) de requisições com parâmetros fora do escopo operacional ótimo.*
