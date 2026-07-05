from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from src.domain.entities import Document, ParsedDocument, Chunk, QueryResult, RetrievalContext

class DocumentParser(ABC):
    @abstractmethod
    def parse(self, file_path: str, document_id: str) -> ParsedDocument:
        """Parses a document file and extracts structural content into ParsedDocument."""
        pass

class TextNormalizer(ABC):
    @abstractmethod
    def normalize(self, text: str, is_ocr: bool) -> str:
        """Normalizes and cleans the extracted text."""
        pass

class Enricher(ABC):
    @abstractmethod
    def enrich(self, document: ParsedDocument) -> ParsedDocument:
        """Enriches parsed document metadata (keywords, categories)."""
        pass

class Chunker(ABC):
    @abstractmethod
    def chunk(self, document: ParsedDocument) -> List[Chunk]:
        """Splits a parsed and normalized document into list of Chunks."""
        pass

class EmbeddingProvider(ABC):
    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """Generates embedding vector for a single text string."""
        pass

    @abstractmethod
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a list of text strings in batch."""
        pass

    @abstractmethod
    def model_version(self) -> str:
        """Returns the version/name of the embedding model."""
        pass

    @abstractmethod
    def dimension(self) -> int:
        """Returns the dimension of the generated embedding vectors."""
        pass

class VectorStore(ABC):
    @abstractmethod
    def upsert_chunks(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        """Stores chunk data and their corresponding vectors."""
        pass

    @abstractmethod
    def delete_document_chunks(self, document_id: str, exclude_version: Optional[str] = None) -> None:
        """Deletes chunks associated with document_id, optionally excluding a specific version."""
        pass

    @abstractmethod
    def search_similarity(self, query_embedding: List[float], filter_metadata: Dict[str, Any], top_k: int) -> List[QueryResult]:
        """Performs vector similarity search, optionally filtering by metadata."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Returns storage stats (number of documents, chunks, size)."""
        pass

    @abstractmethod
    def get_all_chunks(self, filter_metadata: Dict[str, Any]) -> List[Chunk]:
        """Retrieves all chunks matching filter_metadata (without vectors)."""
        pass

class Retriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, filter_metadata: Dict[str, Any], top_k: int) -> List[QueryResult]:
        """Retrieves top relevant chunks for a user query."""
        pass

class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, results: List[QueryResult], top_k: int) -> List[QueryResult]:
        """Re-ranks retrieved query results to improve relevance ordering."""
        pass

class ContextBuilder(ABC):
    @abstractmethod
    def build_context(self, query: str, results: List[QueryResult]) -> RetrievalContext:
        """Compiles final optimized text context for sending to the LLM."""
        pass

class LLMProvider(ABC):
    @abstractmethod
    def generate_response(self, system_prompt: str, context: str, user_query: str) -> str:
        """Generates a text answer based on context using the local LLM engine."""
        pass

class BenchmarkRunner(ABC):
    @abstractmethod
    def run_benchmark(self) -> Dict[str, Any]:
        """Runs quality evaluation benchmark on the current pipeline configuration."""
        pass

class DocumentRepository(ABC):
    @abstractmethod
    def save_document(self, document: Document) -> None:
        """Saves or updates a document status entry."""
        pass

    @abstractmethod
    def get_document(self, document_id: str) -> Optional[Document]:
        """Retrieves a document entry by ID."""
        pass

    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        """Deletes a document entry by ID."""
        pass

    @abstractmethod
    def list_documents(self) -> List[Document]:
        """Lists all registered documents."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Gets document status stats (counts by status, totals)."""
        pass

