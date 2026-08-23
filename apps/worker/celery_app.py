from celery import Celery

from apps.worker.celery_config import CELERY_CONFIG

celery = Celery("adaptive-rag",
                include=[
                    "apps.worker.tasks.health",
                    "apps.worker.tasks.pipeline",
                    "apps.worker.tasks.parse_task",
                    "apps.worker.tasks.embedding_task",
                ]
                )

celery.conf.update(CELERY_CONFIG)

celery.autodiscover_tasks(
    ["apps.worker.tasks"]
)


# include=[
#     "apps.worker.tasks.health",
#     "apps.worker.tasks.parse",
#     "apps.worker.tasks.chunk",
#     "apps.worker.tasks.embedding",
#     "apps.worker.tasks.vector",
#     "apps.worker.tasks.graph",
#     "apps.worker.tasks.completion",
# ]
