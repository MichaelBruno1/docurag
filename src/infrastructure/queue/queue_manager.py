import logging
from typing import Callable, Any, Dict, Optional
from redis import Redis
from rq import Queue
from src.config import settings

logger = logging.getLogger(__name__)

class QueueManager:
    def __init__(self):
        try:
            self.redis_conn = Redis.from_url(settings.REDIS_URL)
            self.queue = Queue("docurag_tasks", connection=self.redis_conn)
            logger.info("Conectado ao Redis com sucesso para fila de tarefas.")
        except Exception as e:
            logger.error(f"Erro ao conectar ao Redis: {e}")
            self.redis_conn = None
            self.queue = None

    def enqueue_job(self, func: Callable, *args: Any, **kwargs: Any) -> Optional[str]:
        """Enqueues a function for asynchronous background processing."""
        if not self.queue:
            logger.error("Fila de tarefas não inicializada (sem conexão com Redis).")
            # If Redis is unavailable, raise exception or return None
            raise RuntimeError("Redis não disponível para processamento assíncrono.")
            
        job = self.queue.enqueue(func, *args, **kwargs)
        logger.info(f"Tarefa {job.id} enfileirada com sucesso para a função {func.__name__}.")
        return job.id

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Retrieves status of a queued job."""
        if not self.queue:
            return {"status": "error", "message": "Fila de tarefas indisponível"}
            
        job = self.queue.fetch_job(job_id)
        if not job:
            return {"status": "not_found", "message": f"Tarefa {job_id} não encontrada"}
            
        return {
            "job_id": job.id,
            "status": job.get_status(),  # 'queued', 'started', 'finished', 'failed'
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            "exc_info": job.exc_info
        }

# Global queue manager instance
queue_manager = QueueManager()
