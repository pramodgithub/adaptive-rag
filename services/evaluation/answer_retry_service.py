from mlflow import trace
from core.llm.prompts.eval_answer_prompt import build_answer_retry_prompt
from core.llm.router import ModelRouter
from services.evaluation.answer_evaluator import AnswerEvaluator


class AnswerRetryService:

    MAX_RETRIES = 1

    def __init__(self):
        self.llm = ModelRouter()
        self.evaluator = AnswerEvaluator()

    @trace
    def generate(self, query: str, prompt: str, context: str):

        response = self.llm.generate_for_node(
            prompt, node_name="answer_generation")

        answer = response["text"]

        evaluation = self.evaluator.evaluate(
            query=query,
            answer=answer,
            context=context
        )

        if evaluation.should_retry:

            retry_prompt = build_answer_retry_prompt(prompt, evaluation)

            response = self.llm.generate_for_node(
                retry_prompt, node_name="answer_retry")

            answer = response["text"]

            evaluation = self.evaluator.evaluate(
                query=query,
                answer=answer,
                context=context
            )

        return answer, response, evaluation
