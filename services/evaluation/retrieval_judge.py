from core.llm.prompts.retrieval_judge_prompt import (
    build_retrieval_judge_prompt,
)
from core.llm.router import ModelRouter
from core.schemas.retrieval import RetrievalJudgeResult
from services.evaluation.retrieval_judge_parser import RetrievalJudgeParser


class RetrievalJudge:

    def __init__(self, llm: ModelRouter | None = None):
        self.llm = llm or ModelRouter()

    def evaluate(
        self,
        query: str,
        context: str,
    ) -> RetrievalJudgeResult:

        prompt = build_retrieval_judge_prompt(
            query=query,
            context=context,
        )

        result = self.llm.generate_for_node(
            prompt,
            node_name="retrieval_judge",
        )

        return RetrievalJudgeParser.parse(
            result["text"],
        )
