from unittest import result

from core.llm.router import ModelRouter
from core.llm.prompts.retrieval_judge_prompt import build_retrieval_judge_prompt
from core.schemas.retrieval import RetrievalJudgeEvaluation
from services.evaluation.parser import EvaluationParser


class RetrievalJudge:

    def __init__(self):

        self.llm = ModelRouter()

    def evaluate(self, query: str, context: str) -> RetrievalJudgeEvaluation:

        prompt = build_retrieval_judge_prompt(
            query,
            context
        )

        result = self.llm.generate(
            prompt
        )

        return EvaluationParser.parsejudge(
            result["text"]
        )
