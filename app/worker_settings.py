"""Worker settings — ARQ queue configuration and Redis connection."""

from __future__ import annotations

from app.config import settings as app_settings


class WorkerSettings:
    """Settings for the ARQ background worker process.

    The worker is responsible for:
    - Document ingestion (parsing, chunking)
    - Embedding generation (vector DB population)
    - Any other CPU/IO-bound background tasks
    """
    # Redis connection
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""

    # Concurrency
    max_burst_jobs: int = 10
    job_timeout: int = 300  # 5 minutes max per job
    poll_delay: float = 0.5  # seconds between queue polls

    # Inference
    inference_url: str = app_settings.inference_url
    inference_model: str = app_settings.inference_model
    embedding_model: str = "nomic-embed-text-v1.5"

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/0"


worker_settings = WorkerSettings()
