import time
import logging
from typing import Dict, Any
import httpx

from src.domain.ports import LLMProvider
from src.config import settings

logger = logging.getLogger(__name__)

class LMStudioLLMProvider(LLMProvider):
    def __init__(self):
        self.url = f"{settings.LM_STUDIO_URL}/chat/completions"
        self.model_name = settings.LLM_MODEL_NAME

    def generate_response(self, system_prompt: str, context: str, user_query: str) -> str:
        # Chat completions JSON payload structure matching OpenAI spec
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Contexto:\n{context}\n\nPergunta:\n{user_query}"}
            ],
            "temperature": 0.0  # Factual consistency over creativity (user constraint)
        }

        max_retries = 3
        backoff = 1.0

        # Send HTTP request with connection retries and exponential backoff
        with httpx.Client(timeout=90.0) as client:
            for attempt in range(max_retries):
                try:
                    logger.info(f"Enviando prompt ao LM Studio (Tentativa {attempt + 1}/{max_retries})")
                    start_time = time.time()
                    
                    response = client.post(self.url, json=payload)
                    latency = time.time() - start_time

                    if response.status_code == 200:
                        data = response.json()
                        answer = data["choices"][0]["message"]["content"]
                        
                        # Extract and log prompt/generation token usage
                        usage = data.get("usage", {})
                        logger.info(
                            f"Resposta da LLM recebida com sucesso em {latency:.2f}s. "
                            f"Tokens: prompt={usage.get('prompt_tokens', 0)}, "
                            f"completion={usage.get('completion_tokens', 0)}"
                        )
                        return answer
                    else:
                        logger.warning(
                            f"LM Studio retornou erro HTTP {response.status_code} na tentativa {attempt + 1}: {response.text}"
                        )
                except httpx.RequestError as e:
                    logger.warning(
                        f"Falha de comunicação/rede com LM Studio na tentativa {attempt + 1}: {e}"
                    )

                # Wait before retrying
                if attempt < max_retries - 1:
                    logger.info(f"Aguardando {backoff}s antes de tentar novamente...")
                    time.sleep(backoff)
                    backoff *= 2

        logger.error("Todas as tentativas de chamada ao LM Studio falharam.")
        raise RuntimeError("Não foi possível obter resposta da LLM do LM Studio após múltiplas tentativas.")
