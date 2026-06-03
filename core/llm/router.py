from .gemini_llm import GeminiLLM
from .ollama_llm import OllamaLLM
import mlflow


class ModelRouter:

    def __init__(self):
        self.primary = OllamaLLM()
        self.fallback = GeminiLLM()

    @mlflow.trace
    def generate(self, prompt):

        try:
            result = self.primary.generate(prompt)
            mlflow.set_tag("provider", "ollama")
            mlflow.set_tag("model", self.primary.model_name)
            mlflow.set_tag("fallback_used", False)
            return result

        except Exception as e:
            mlflow.set_tag("provider", "gemini")
            mlflow.set_tag("model", self.fallback.model_name)
            mlflow.set_tag("fallback_used", True)
            mlflow.set_tag("fallback_reason", str(e))

            result = self.fallback.generate(prompt)
            result["fallback"] = True
            return result

    def generate_for_node(self, prompt, node_name: str):

        result = self.generate(prompt)

        mlflow.set_tag("node", node_name)

        total_tokens = result.get("total_tokens", 0)
        mlflow.log_metric(
            f"{node_name}_tokens",
            total_tokens
        )

        return result
