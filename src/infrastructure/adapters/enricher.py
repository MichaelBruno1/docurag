import datetime
import logging
from typing import Dict, Any
import yake

from src.domain.entities import ParsedDocument
from src.domain.ports import Enricher

logger = logging.getLogger(__name__)

class YakeEnricher(Enricher):
    def __init__(self):
        # Configure YAKE for Portuguese keyword extraction
        self.kw_extractor = yake.KeywordExtractor(
            lan="pt",
            n=2,          # Max length of keywords (bi-grams)
            dedupLim=0.9, # Deduplication threshold
            top=5,        # Number of keywords to extract per section
            features=None
        )

    def enrich(self, document: ParsedDocument) -> ParsedDocument:
        logger.info(f"Enriquecendo documento {document.document_id} com metadados e palavras-chave.")
        
        # 1. Classify Category based on title and early content
        category = self._detect_category(document)
        document.raw_metadata["categoria"] = category
        
        # 2. Extract author and dates from raw metadata or apply fallback
        author = document.raw_metadata.get("author") or document.raw_metadata.get("creator") or "desconhecido"
        # Remove null characters or control chars from author
        author = str(author).replace("\x00", "").strip()
        if not author:
            author = "desconhecido"
            
        created_at_str = document.raw_metadata.get("created_at") or document.raw_metadata.get("creation_date")
        if not created_at_str:
            created_at_str = datetime.datetime.utcnow().isoformat()
            
        document.raw_metadata["autor"] = author
        document.raw_metadata["data_original"] = created_at_str
        document.raw_metadata["idioma"] = "pt-BR"
        
        # 3. Extract keywords per section
        for section in document.sections:
            content_text = section.content or ""
            if len(content_text.strip()) > 30:
                try:
                    kws = self.kw_extractor.extract_keywords(content_text)
                    # Extract string keyword from (keyword, score) tuple
                    section_kws = [k[0] for k in kws]
                except Exception as e:
                    logger.warning(f"Falha ao extrair palavras-chave YAKE: {e}")
                    section_kws = []
            else:
                section_kws = []
            
            # Dynamically attach keywords list to section for Chunker propagation
            setattr(section, "keywords", section_kws)
            
        return document

    def _detect_category(self, document: ParsedDocument) -> str:
        title = (document.title or "").lower()
        first_content = ""
        if document.sections:
            first_content = (document.sections[0].content or "")[:1000].lower()
            
        text_to_search = f"{title} {first_content}"
        
        # Simple heuristic mappings matching the taxonomy
        heuristics = {
            "Manual": ["manual", "guia do usuário", "instruções de uso", "guia de"],
            "Política": ["política", "diretriz", "norma interna", "diretrizes"],
            "Procedimento": ["procedimento", "processo", "pop", "passo a passo"],
            "Especificação Técnica": ["especificação", "spec", "requisitos técnicos", "arquitetura", "projeto técnico"],
            "Relatório": ["relatório", "análise", "resultado", "levantamento", "reporte"]
        }
        
        for category, patterns in heuristics.items():
            for pattern in patterns:
                if pattern in text_to_search:
                    return category
                    
        return "Outro"
