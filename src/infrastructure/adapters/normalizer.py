import re
from src.domain.ports import TextNormalizer

class RegexTextNormalizer(TextNormalizer):
    def normalize(self, text: str, is_ocr: bool) -> str:
        if not text:
            return ""
        
        # 1. Remove invalid control characters (keep \n, \t, \r)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # 2. Fix broken hyphenation from line wrapping (e.g., "infor-\nmação" -> "informação")
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
        
        # 3. Clean spaces inside words and multiple spaces
        text = re.sub(r'[ \t]+', ' ', text)
        
        # 4. Normalize redundant blank lines (keep maximum 2 newlines to preserve paragraphs)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 5. Apply OCR-specific corrections if text originates from OCR
        if is_ocr:
            text = self._apply_ocr_rules(text)
            
        return text.strip()
        
    def _apply_ocr_rules(self, text: str) -> str:
        # Correct letter 'O' confused with digit '0' inside numbers:
        # e.g., "R$ 1.O00" -> "R$ 1.000", "1O%" -> "10%"
        text = re.sub(r'(\d)[O](\d)', r'\g<1>0\g<2>', text)
        text = re.sub(r'(\d)O', r'\g<1>0', text)
        text = re.sub(r'O(\d)', r'0\g<1>', text)
        
        # Correct letters 'l' or 'I' confused with digit '1' inside numbers:
        # e.g., "1.l00" -> "1.100" or "3I2" -> "312"
        text = re.sub(r'(\d)[lI](\d)', r'\g<1>1\g<2>', text)
        
        return text
