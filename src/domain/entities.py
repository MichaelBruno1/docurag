from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

@dataclass
class ParsedSection:
    heading: Optional[str]
    level: int
    content: str
    page_number: Optional[int] = None
    tables: List[Any] = field(default_factory=list)  # List of tables represented structuredly

@dataclass
class ParsedDocument:
    document_id: str
    source_format: str
    title: Optional[str]
    sections: List[ParsedSection]
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Document:
    document_id: str
    nome_arquivo: str
    formato: str
    tamanho_bytes: int
    created_at: datetime
    status: str  # 'enfileirado', 'processando', 'concluido', 'erro'
    error_message: Optional[str] = None
    categoria: Optional[str] = None
    autor: Optional[str] = None
    data_original: Optional[str] = None

@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    content: str
    tokens_count: int
    nome_arquivo: Optional[str] = None
    capitulo: Optional[str] = None
    secao: Optional[str] = None
    subtitulo: Optional[str] = None
    pagina: Optional[int] = None
    origem_ocr: bool = False
    confianca_ocr: Optional[float] = None
    palavras_chave: List[str] = field(default_factory=list)
    chunk_anterior_id: Optional[str] = None
    chunk_seguinte_id: Optional[str] = None
    chunk_pai_id: Optional[str] = None
    embedding_version: Optional[str] = None
    
    def to_payload(self) -> Dict[str, Any]:
        """Converts chunk metadata to a dictionary payload for Qdrant storage."""
        return {
            "document_id": self.document_id,
            "nome_arquivo": self.nome_arquivo,
            "content": self.content,
            "tokens_count": self.tokens_count,
            "capitulo": self.capitulo,
            "secao": self.secao,
            "subtitulo": self.subtitulo,
            "pagina": self.pagina,
            "origem_ocr": self.origem_ocr,
            "confianca_ocr": self.confianca_ocr,
            "palavras_chave": self.palavras_chave,
            "chunk_anterior_id": self.chunk_anterior_id,
            "chunk_seguinte_id": self.chunk_seguinte_id,
            "chunk_pai_id": self.chunk_pai_id,
            "embedding_version": self.embedding_version
        }

@dataclass
class QueryResult:
    chunk: Chunk
    score: float

@dataclass
class RetrievalContext:
    context_text: str
    used_chunks: List[QueryResult]
    discarded_chunks: List[QueryResult]

@dataclass
class Citation:
    document_id: str
    nome_arquivo: str
    secao: Optional[str] = None
    pagina: Optional[int] = None
