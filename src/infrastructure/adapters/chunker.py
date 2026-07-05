import re
import hashlib
import logging
from typing import List, Dict, Any, Optional
import numpy as np

from src.domain.entities import ParsedDocument, Chunk, ParsedSection
from src.domain.ports import Chunker, EmbeddingProvider
from src.config import settings
from transformers import AutoTokenizer

logger = logging.getLogger(__name__)

# Global tokenizer cache for Qwen
_tokenizer = None

def get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        try:
            # Load Qwen tokenizer which has 8k context support
            _tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct", trust_remote_code=True)
            logger.info("Tokenizer do Qwen carregado com sucesso.")
        except Exception as e:
            logger.warning(f"Erro ao carregar o tokenizer do Qwen do HF (provavelmente offline). Usando fallback de palavras: {e}")
            class FallbackTokenizer:
                def encode(self, text: str) -> list:
                    words = text.split()
                    return [0] * int(len(words) * 1.3)
            _tokenizer = FallbackTokenizer()
    return _tokenizer

def count_tokens(text: str) -> int:
    try:
        t = get_tokenizer()
        return len(t.encode(text))
    except Exception:
        return int(len(text.split()) * 1.3)


class HybridChunker(Chunker):
    def __init__(self, embedding_provider: EmbeddingProvider, target_size: Optional[int] = None, overlap: Optional[int] = None):
        self.embedding_provider = embedding_provider
        self.target_size = target_size or settings.CHUNK_SIZE_TARGET
        self.overlap = overlap or settings.CHUNK_OVERLAP

    def chunk(self, document: ParsedDocument) -> List[Chunk]:
        logger.info(f"Iniciando chunking híbrido para documento {document.document_id}.")
        self.current_title = document.title
        chunks = []
        
        # Propagate metadata from enricher
        doc_metadata = {
            "categoria": document.raw_metadata.get("categoria", "Outro"),
            "autor": document.raw_metadata.get("autor", "desconhecido"),
            "data_original": document.raw_metadata.get("data_original"),
            "idioma": document.raw_metadata.get("idioma", "pt-BR"),
            "ocr_applied": document.raw_metadata.get("ocr_applied", False)
        }
        
        # We iterate through sections
        for s_idx, section in enumerate(document.sections):
            section_chunks = []
            
            # Check if section has tables and split them adaptively
            if section.tables:
                for table in section.tables:
                    table_chunks = self._chunk_table_adaptively(table, document.document_id, section)
                    section_chunks.extend(table_chunks)
            
            # Process main text content of section
            text_content = section.content or ""
            if text_content.strip():
                text_chunks = self._chunk_text_semantically(text_content, document.document_id, section)
                section_chunks.extend(text_chunks)
                
            # Add to main list
            chunks.extend(section_chunks)
            
        # Post-process to set sequential relations (chunk_anterior_id, chunk_seguinte_id)
        for i in range(len(chunks)):
            if i > 0:
                chunks[i].chunk_anterior_id = chunks[i-1].chunk_id
            if i < len(chunks) - 1:
                chunks[i].chunk_seguinte_id = chunks[i+1].chunk_id
                
        logger.info(f"Chunking concluído. Gerados {len(chunks)} chunks para o documento {document.document_id}.")
        return chunks

    def _chunk_table_adaptively(self, table: List[List[str]], document_id: str, section: ParsedSection) -> List[Chunk]:
        # Table adaptive chunking
        if not table:
            return []
            
        headers = table[0]
        rows = table[1:]
        
        # Helper to check token size
        def format_grid(h, r):
            from src.infrastructure.adapters.parsers import format_grid_as_markdown_table
            return format_grid_as_markdown_table([h] + r)
            
        table_str = format_grid(headers, rows)
        if count_tokens(table_str) <= self.target_size:
            # Fits in one chunk
            return [self._create_chunk(table_str, document_id, section, page=section.page_number)]
            
        # If it doesn't fit, split by row blocks
        chunks = []
        current_rows = []
        for row in rows:
            temp_rows = current_rows + [row]
            temp_str = format_grid(headers, temp_rows)
            if count_tokens(temp_str) > self.target_size and current_rows:
                # Flush current block
                block_str = format_grid(headers, current_rows)
                chunks.append(self._create_chunk(block_str, document_id, section, page=section.page_number))
                current_rows = [row]
            else:
                current_rows.append(row)
                
        if current_rows:
            block_str = format_grid(headers, current_rows)
            chunks.append(self._create_chunk(block_str, document_id, section, page=section.page_number))
            
        return chunks

    def _chunk_text_semantically(self, text: str, document_id: str, section: ParsedSection) -> List[Chunk]:
        tokens_count = count_tokens(text)
        if tokens_count <= self.target_size:
            # Already fits, no need to split semantically
            return [self._create_chunk(text, document_id, section, page=section.page_number)]
            
        # Semantic splitting using sentence embeddings
        # 1. Split into sentences
        # Simple regex for sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 1:
            # Fallback to character chunking if we cannot split by sentence
            return self._fallback_character_split(text, document_id, section)
            
        try:
            # 2. Get embeddings for each sentence
            embeddings = self.embedding_provider.get_embeddings(sentences)
            
            # 3. Calculate cosine similarity between adjacent sentences
            similarities = []
            for i in range(len(embeddings) - 1):
                vec1 = np.array(embeddings[i])
                vec2 = np.array(embeddings[i+1])
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)
                if norm1 > 0 and norm2 > 0:
                    similarity = np.dot(vec1, vec2) / (norm1 * norm2)
                else:
                    similarity = 0.0
                similarities.append(similarity)
                
            # 4. Determine splitting indices based on low similarities
            # Group sentences into chunks keeping size under target_size
            chunks_text = []
            current_chunk_sentences = []
            
            for idx, sentence in enumerate(sentences):
                current_chunk_sentences.append(sentence)
                candidate_text = " ".join(current_chunk_sentences)
                
                # If adding this sentence exceeds target size, split
                if count_tokens(candidate_text) > self.target_size and len(current_chunk_sentences) > 1:
                    # Pop the last sentence and flush current chunk
                    current_chunk_sentences.pop()
                    chunks_text.append(" ".join(current_chunk_sentences))
                    current_chunk_sentences = [sentence]
                # Also check if similarity drops significantly (semantic split)
                elif idx < len(similarities):
                    # If similarity is below median similarity, and chunk is of reasonable size, split
                    # To be conservative, split if similarity is low (< 0.6) and we have enough content
                    if similarities[idx] < 0.6 and count_tokens(candidate_text) >= self.target_size * 0.5:
                        chunks_text.append(" ".join(current_chunk_sentences))
                        current_chunk_sentences = []
                        
            if current_chunk_sentences:
                chunks_text.append(" ".join(current_chunk_sentences))
                
            return [self._create_chunk(t, document_id, section, page=section.page_number) for t in chunks_text if t.strip()]
            
        except Exception as e:
            logger.warning(f"Erro ao computar embeddings para chunking semântico: {e}. Usando fallback por parágrafos.")
            return self._fallback_paragraph_split(text, document_id, section)

    def _fallback_paragraph_split(self, text: str, document_id: str, section: ParsedSection) -> List[Chunk]:
        paragraphs = text.split("\n\n")
        chunks = []
        current_block = []
        
        for p in paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue
            temp_block = current_block + [p_strip]
            temp_str = "\n\n".join(temp_block)
            if count_tokens(temp_str) > self.target_size and current_block:
                chunks.append(self._create_chunk("\n\n".join(current_block), document_id, section, page=section.page_number))
                current_block = [p_strip]
            else:
                current_block.append(p_strip)
                
        if current_block:
            chunks.append(self._create_chunk("\n\n".join(current_block), document_id, section, page=section.page_number))
            
        return chunks

    def _fallback_character_split(self, text: str, document_id: str, section: ParsedSection) -> List[Chunk]:
        # Simple fallback character chunking
        chunks = []
        start = 0
        char_limit = int(self.target_size * 4) # Approximation
        step = char_limit - int(self.overlap * 4)
        
        while start < len(text):
            end = start + char_limit
            chunk_text = text[start:end]
            chunks.append(self._create_chunk(chunk_text, document_id, section, page=section.page_number))
            start += step
            
        return chunks

    def _create_chunk(self, content: str, document_id: str, section: ParsedSection, page: Optional[int]) -> Chunk:
        # Determine unique deterministic ID based on document and content hash
        hasher = hashlib.sha256()
        hasher.update(f"{document_id}:{content}".encode("utf-8"))
        chunk_id = hasher.hexdigest()
        
        tokens_count = count_tokens(content)
        
        # Propagate YAKE keywords and section hierarchy
        keywords = getattr(section, "keywords", [])
        
        return Chunk(
            chunk_id=chunk_id,
            document_id=document_id,
            content=content,
            tokens_count=tokens_count,
            nome_arquivo=getattr(self, "current_title", None),
            capitulo=None, # Filled if hierarchical level exists
            secao=section.heading,
            subtitulo=None,
            pagina=page,
            origem_ocr=False, # Filled later in indexer based on raw doc
            confianca_ocr=None,
            palavras_chave=keywords,
            chunk_pai_id=section.heading,
            embedding_version=self.embedding_provider.model_version()
        )
