import json
import re
import mlflow
from mlflow import trace

from core.llm.prompts.answer_evaluator_prompt import build_answer_evaluator_prompt
from core.schemas.evaluation import AnswerEvaluation
from core.llm.router import ModelRouter


class AnswerEvaluator:

    MIN_CONFIDENCE = 0.70

    def __init__(self):
        self.llm = ModelRouter()

    @trace
    def evaluate(self, query: str, answer: str, context: str) -> AnswerEvaluation:

        prompt = build_answer_evaluator_prompt(
            query=query,
            context=context,
            answer=answer
        )

        response = self.llm.generate_for_node(
            prompt, node_name="answer_evaluation")

        result = self.extract_json(response["text"])

        # --- Non-LLM Check 1: Keyword Overlap ---
        context_text = context.lower()
        answer_words = set(answer.lower().split())
        context_words = set(context_text.split())
        overlap_score = (
            len(answer_words & context_words) / len(answer_words)
            if answer_words else 0
        )

        # --- Non-LLM Check 2: Answer Length Sanity ---
        too_short = len(answer.split()) < 10

        # --- Non-LLM Check 3: Refusal Detection ---
        refusal_phrases = [
            "i don't know", "i cannot", "no information",
            "not found in context", "i'm not sure"
        ]
        is_refusal = any(p in answer.lower() for p in refusal_phrases)

        # --- Adjust Confidence ---
        adjusted_confidence = result["confidence"]
        if overlap_score < 0.25:
            adjusted_confidence *= 0.7
        if too_short or is_refusal:
            adjusted_confidence *= 0.5

        # --- Decide WHY it failed → drives routing ---
        context_is_poor = (
            overlap_score < 0.25      # context had little relevance
            or is_refusal             # LLM found nothing useful in context
            or not result["grounded"]  # LLM says answer not in context
        )

        generation_is_poor = (
            adjusted_confidence < self.MIN_CONFIDENCE  # confident context exists
            # but answer was incomplete
            or not result["complete"]
            or too_short                               # or too vague
        )

        # --- Routing logic ---
        #
        # context_is_poor=True  → no point regenerating with same bad context
        #                        → go back to retrieval
        #
        # generation_is_poor=True → context was ok, generation drifted
        #                         → retry generation with stricter prompt
        #
        # Priority: context failure wins over generation failure
        # because fixing generation with bad context never helps

        if context_is_poor:
            should_retry = True
            retry_type = "retrieval"
        elif generation_is_poor:
            should_retry = True
            retry_type = "generation"
        else:
            should_retry = False
            retry_type = None

        mlflow.log_metric("answer_confidence", result["confidence"])
        return AnswerEvaluation(
            grounded=result["grounded"],
            complete=result["complete"],
            confidence=result["confidence"],
            should_retry=should_retry,
            reason=result["reason"],
            retry_type=retry_type
        )

    def extract_json(self, text: str) -> dict:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON found")
        return json.loads(match.group())
