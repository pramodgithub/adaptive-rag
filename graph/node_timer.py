import time
import mlflow


def time_node(node_name: str, func, *args, **kwargs):
    start = time.time()
    result = func(*args, **kwargs)
    duration = round(time.time() - start, 3)

    mlflow.log_metric(f"{node_name}_duration", duration)

    return result, duration
