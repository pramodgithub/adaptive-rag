MAX_RETRIES = 2


def should_retry_retrieval(state):

    should_retry = (
        state["retrieval"]["should_retry"]
    )

    retries = state["retry_count"]

    if should_retry and retries < MAX_RETRIES:
        return "rewrite"

    return "generate"
