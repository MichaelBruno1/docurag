import os
import sqlite3
import datetime
import logging
from typing import List, Dict, Any, Optional

from src.domain.entities import Document
from src.domain.ports import DocumentRepository
from src.config import settings

logger = logging.getLogger(__name__)

class SQLiteDocumentRepository(DocumentRepository):
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DATABASE_PATH
        
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    nome_arquivo TEXT NOT NULL,
                    formato TEXT NOT NULL,
                    tamanho_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    categoria TEXT,
                    autor TEXT,
                    data_original TEXT
                )
            """)
            conn.commit()
        logger.info(f"Banco de dados SQLite inicializado em {self.db_path}")

    def save_document(self, document: Document) -> None:
        created_at_str = document.created_at.isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents (
                    document_id, nome_arquivo, formato, tamanho_bytes, created_at, status, error_message, categoria, autor, data_original
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.document_id,
                    document.nome_arquivo,
                    document.formato,
                    document.tamanho_bytes,
                    created_at_str,
                    document.status,
                    document.error_message,
                    document.categoria,
                    document.autor,
                    document.data_original
                )
            )
            conn.commit()
        logger.debug(f"Documento {document.document_id} salvo/atualizado no repositório.")

    def get_document(self, document_id: str) -> Optional[Document]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,)
            ).fetchone()
            
            if row is None:
                return None
                
            return Document(
                document_id=row["document_id"],
                nome_arquivo=row["nome_arquivo"],
                formato=row["formato"],
                tamanho_bytes=row["tamanho_bytes"],
                created_at=datetime.datetime.fromisoformat(row["created_at"]),
                status=row["status"],
                error_message=row["error_message"],
                categoria=row["categoria"],
                autor=row["autor"],
                data_original=row["data_original"]
            )

    def delete_document(self, document_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
            conn.commit()
        logger.info(f"Registro do documento {document_id} removido do repositório.")

    def list_documents(self) -> List[Document]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
            documents = []
            for row in rows:
                doc = Document(
                    document_id=row["document_id"],
                    nome_arquivo=row["nome_arquivo"],
                    formato=row["formato"],
                    tamanho_bytes=row["tamanho_bytes"],
                    created_at=datetime.datetime.fromisoformat(row["created_at"]),
                    status=row["status"],
                    error_message=row["error_message"],
                    categoria=row["categoria"],
                    autor=row["autor"],
                    data_original=row["data_original"]
                )
                documents.append(doc)
            return documents

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            total_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            total_bytes = conn.execute("SELECT SUM(tamanho_bytes) FROM documents").fetchone()[0] or 0
            
            # Counts by status
            status_rows = conn.execute("SELECT status, COUNT(*) as cnt FROM documents GROUP BY status").fetchall()
            status_counts = {r["status"]: r["cnt"] for r in status_rows}
            
            return {
                "total_documents": total_docs,
                "total_bytes": total_bytes,
                "status_counts": {
                    "enfileirado": status_counts.get("enfileirado", 0),
                    "processando": status_counts.get("processando", 0),
                    "concluido": status_counts.get("concluido", 0),
                    "erro": status_counts.get("erro", 0)
                }
            }
