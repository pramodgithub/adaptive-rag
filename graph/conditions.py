def should_retry_retrieval(state):

    if not state["retrieval"].sufficient:
        return "rewrite"

    return "generate"


MAX_RETRIES = 2
JUDGE_THRESHOLD = 0.50


def should_run_retrieval_judge(state):
    retrieval = state["retrieval_evaluation"]
    retry_count = state.get("retry_count", 0)

    if retrieval.sufficient:
        return "generate"

    if retry_count >= MAX_RETRIES:
        return "insufficient"

    if retrieval.confidence >= JUDGE_THRESHOLD:
        return "judge"

    return "rewrite"


def should_retry_after_judge(state):
    judgment = state["retrieval_judgment"]
    retry_count = state.get("retry_count", 0)

    if judgment.sufficient:
        return "generate"

    if retry_count >= MAX_RETRIES:
        return "insufficient"

    return "rewrite"
