from core.llm.prompts.eval_retry_prompt import build_eval_retry_prompt
from core.llm.router import ModelRouter
from services.evaluation.answer_evaluator import AnswerEvaluator


class AnswerRetryService:

    MAX_RETRIES = 1

    def __init__(self):
        self.llm = ModelRouter()
        self.evaluator = AnswerEvaluator()

    def generate(self, query: str, prompt: str, context: str):

        response = self.llm.generate(prompt)

        answer = response["text"]

        evaluation = self.evaluator.evaluate(
            query=query,
            answer=answer,
            context=context
        )

        if evaluation.should_retry:

            retry_prompt = build_eval_retry_prompt(prompt)

            response = self.llm.generate(retry_prompt)

            answer = response["text"]

            evaluation = self.evaluator.evaluate(
                query=query,
                answer=answer,
                context=context
            )

        return answer, response, evaluation
