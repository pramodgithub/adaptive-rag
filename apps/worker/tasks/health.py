from apps.worker.celery_app import celery


@celery.task(name="health.ping")
def ping():

    return {
        "status": "healthy"
    }
