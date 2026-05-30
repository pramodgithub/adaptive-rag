MAX_RETRIES = 2

MIN_COVERAGE = 0.6


def should_retry_retrieval(state):

    retrieval = state["retrieval"]

    judge = state["retrieval_judge"]

    retries = state["retry_count"]

    if retries >= MAX_RETRIES:
        return "generate"

    if retrieval["should_retry"]:
        return "rewrite"

    if not judge.relevant:
        return "rewrite"

    if judge.coverage < MIN_COVERAGE:
        return "rewrite"

    return "generate"


# def should_retry_answer(state) -> str:
#     eval = state["eval"]

#     if not eval.should_retry:
#         return "end"

#     if eval.retry_type == "retrieval":
#         return "rewrite"       # → goes back to retrieval node

#     if eval.retry_type == "generation":
#         return "regenerate"    # → retries generation with better prompt

#     return "end"
