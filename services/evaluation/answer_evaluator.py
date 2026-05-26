import json
import re

from core.llm.prompts.answer_evaluator_prompt import build_answer_evaluator_prompt
from core.schemas.evaluation import AnswerEvaluation
from core.llm.router import ModelRouter


class AnswerEvaluator:

    MIN_CONFIDENCE = 0.70

    def __init__(self):
        self.llm = ModelRouter()

    def evaluate(self, query: str, answer: str, context: str) -> AnswerEvaluation:

        prompt = build_answer_evaluator_prompt(
            query=query,
            context=context,
            answer=answer
        )

        response = self.llm.generate(prompt)

        result = self.extract_json(response["text"])

        should_retry = (
            not result["grounded"]
            or result["confidence"] < self.MIN_CONFIDENCE
        )

        return AnswerEvaluation(
            grounded=result["grounded"],
            complete=result["complete"],
            confidence=result["confidence"],
            should_retry=should_retry,
            reason=result["reason"]
        )

    def extract_json(self, text: str) -> dict:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON found")
        return json.loads(match.group())
