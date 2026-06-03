from core.schemas.evaluation import AnswerEvaluation


def build_answer_retry_prompt(prompt, eval_result) -> str:

   # Build specific guidance from what actually failed
    failure_reasons = []

    if not eval_result.grounded:
        failure_reasons.append(
            "- Your previous answer contained claims not supported by context. "
            "Only state what the context explicitly says."
        )

    if eval_result.confidence < 0.70:
        failure_reasons.append(
            "- Your previous answer was uncertain. "
            "If context is insufficient, say exactly what is and isn't covered."
        )

    if not eval_result.complete:
        failure_reasons.append(
            "- Your previous answer was incomplete. "
            f"Evaluator noted: {eval_result.reason}"
        )

    failure_guidance = "\n".join(failure_reasons)

    return f"""
        Your previous answer failed evaluation for these reasons:
        {failure_guidance}

        Rules for this attempt:
        - Use only information explicitly present in the context.
        - Do not infer, assume, or add external knowledge.
        - If context does not cover part of the question, say so explicitly.
        - Be specific — cite which part of context supports each claim.

        {prompt}
    """
