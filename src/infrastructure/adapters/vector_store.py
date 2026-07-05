import os
import uuid
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.domain.entities import Chunk, QueryResult
from src.domain.ports import VectorStore
from src.config import settings

logger = logging.getLogger(__name__)

class QdrantVectorStore(VectorStore):
    COLLECTION_NAME = "docurag_chunks"

    def __init__(self, path: Optional[str] = None):
        self.path = path or settings.QDRANT_PATH
        self._persistent_client: Optional[QdrantClient] = None
        # If in-memory mode, keep a single client instance to prevent DB destruction
        if self.path == ":memory:":
            self._persistent_client = QdrantClient(path=":memory:")

    def _get_client(self) -> QdrantClient:
        if self._persistent_client is not None:
            return self._persistent_client
        return QdrantClient(path=self.path)

    def _close_client(self, client: QdrantClient) -> None:
        if self._persistent_client is None:
            client.close()

    def _ensure_collection(self, client: QdrantClient, vector_size: int) -> None:
        try:
            client.get_collection(self.COLLECTION_NAME)
        except Exception:
            logger.info(f"Coleção '{self.COLLECTION_NAME}' não existe. Criando com dimensão {vector_size}.")
            client.recreate_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )

    def upsert_chunks(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        if not chunks:
            return
            
        vector_size = len(embeddings[0])
        client = self._get_client()
        try:
            self._ensure_collection(client, vector_size)
            
            points = []
            for chunk, emb in zip(chunks, embeddings):
                # Qdrant requires UUID (string) or 64-bit integer.
                # We map our deterministic SHA-256 chunk_id to a deterministic UUID.
                qdrant_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
                
                payload = chunk.to_payload()
                # Store original chunk_id in payload for reconstruction
                payload["chunk_id"] = chunk.chunk_id
                
                # Check for dynamic version_timestamp from ingestion
                if hasattr(chunk, "version_timestamp"):
                    payload["version_timestamp"] = getattr(chunk, "version_timestamp")
                
                points.append(models.PointStruct(
                    id=qdrant_uuid,
                    vector=emb,
                    payload=payload
                ))
                
            client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=points
            )
            logger.info(f"Upsert de {len(chunks)} chunks realizado com sucesso no Qdrant.")
        except Exception as e:
            logger.error(f"Falha ao realizar upsert no Qdrant: {e}")
            raise e
        finally:
            self._close_client(client)

    def delete_document_chunks(self, document_id: str, exclude_version: Optional[str] = None) -> None:
        client = self._get_client()
        try:
            try:
                client.get_collection(self.COLLECTION_NAME)
            except Exception:
                return # Collection doesn't exist yet, nothing to delete
                
            must_conditions = [
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id)
                )
            ]
            must_not_conditions = []
            if exclude_version:
                must_not_conditions.append(
                    models.FieldCondition(
                        key="version_timestamp",
                        match=models.MatchValue(value=exclude_version)
                    )
                )
                
            client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=models.Filter(
                    must=must_conditions,
                    must_not=must_not_conditions if must_not_conditions else None
                )
            )
            logger.info(f"Removidos chunks do documento {document_id} do Qdrant (excluindo versão {exclude_version}).")
        except Exception as e:
            logger.error(f"Erro ao remover chunks do documento {document_id}: {e}")
            raise e
        finally:
            self._close_client(client)

    def search_similarity(self, query_embedding: List[float], filter_metadata: Dict[str, Any], top_k: int) -> List[QueryResult]:
        client = self._get_client()
        try:
            try:
                client.get_collection(self.COLLECTION_NAME)
            except Exception:
                logger.warning(f"Busca falhou: coleção '{self.COLLECTION_NAME}' não existe.")
                return []
                
            # Build filters
            filter_conditions = []
            for key, val in filter_metadata.items():
                if val is not None:
                    filter_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=val)
                        )
                    )
            q_filter = models.Filter(must=filter_conditions) if filter_conditions else None
            
            response = client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=query_embedding,
                query_filter=q_filter,
                limit=top_k
            )
            
            results = []
            for hit in response.points:
                payload = hit.payload
                chunk = Chunk(
                    chunk_id=payload.get("chunk_id", str(hit.id)),
                    document_id=payload.get("document_id"),
                    nome_arquivo=payload.get("nome_arquivo"),
                    content=payload.get("content", ""),
                    tokens_count=payload.get("tokens_count", 0),
                    capitulo=payload.get("capitulo"),
                    secao=payload.get("secao"),
                    subtitulo=payload.get("subtitulo"),
                    pagina=payload.get("pagina"),
                    origem_ocr=payload.get("origem_ocr", False),
                    confianca_ocr=payload.get("confianca_ocr"),
                    palavras_chave=payload.get("palavras_chave", []),
                    chunk_anterior_id=payload.get("chunk_anterior_id"),
                    chunk_seguinte_id=payload.get("chunk_seguinte_id"),
                    chunk_pai_id=payload.get("chunk_pai_id"),
                    embedding_version=payload.get("embedding_version")
                )
                results.append(QueryResult(chunk=chunk, score=hit.score))
            return results
        except Exception as e:
            logger.error(f"Erro ao buscar similaridade no Qdrant: {e}")
            raise e
        finally:
            self._close_client(client)

    def get_stats(self) -> Dict[str, Any]:
        client = self._get_client()
        try:
            try:
                collection_info = client.get_collection(self.COLLECTION_NAME)
                points_count = collection_info.points_count
            except Exception:
                points_count = 0
                
            return {
                "total_chunks": points_count,
                "collection_status": "active" if points_count > 0 else "empty"
            }
        finally:
            self._close_client(client)

    def get_all_chunks(self, filter_metadata: Dict[str, Any]) -> List[Chunk]:
        client = self._get_client()
        try:
            try:
                client.get_collection(self.COLLECTION_NAME)
            except Exception:
                logger.warning(f"Scroll falhou: coleção '{self.COLLECTION_NAME}' não existe.")
                return []
                
            # Build filters
            filter_conditions = []
            for key, val in filter_metadata.items():
                if val is not None:
                    filter_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=val)
                        )
                    )
            q_filter = models.Filter(must=filter_conditions) if filter_conditions else None
            
            # Scroll chunks page by page (limit 100 per page)
            chunks = []
            next_page = None
            while True:
                response, next_page = client.scroll(
                    collection_name=self.COLLECTION_NAME,
                    scroll_filter=q_filter,
                    limit=100,
                    with_payload=True,
                    with_vectors=False,
                    offset=next_page
                )
                for record in response:
                    payload = record.payload
                    chunk = Chunk(
                        chunk_id=payload.get("chunk_id", str(record.id)),
                        document_id=payload.get("document_id"),
                        nome_arquivo=payload.get("nome_arquivo"),
                        content=payload.get("content", ""),
                        tokens_count=payload.get("tokens_count", 0),
                        capitulo=payload.get("capitulo"),
                        secao=payload.get("secao"),
                        subtitulo=payload.get("subtitulo"),
                        pagina=payload.get("pagina"),
                        origem_ocr=payload.get("origem_ocr", False),
                        confianca_ocr=payload.get("confianca_ocr"),
                        palavras_chave=payload.get("palavras_chave", []),
                        chunk_anterior_id=payload.get("chunk_anterior_id"),
                        chunk_seguinte_id=payload.get("chunk_seguinte_id"),
                        chunk_pai_id=payload.get("chunk_pai_id"),
                        embedding_version=payload.get("embedding_version")
                    )
                    chunks.append(chunk)
                if not next_page:
                    break
            return chunks
        except Exception as e:
            logger.error(f"Erro ao recuperar todos os chunks no Qdrant: {e}")
            raise e
        finally:
            self._close_client(client)
