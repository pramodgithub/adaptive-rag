from .gemini_llm import GeminiLLM
from .ollama_llm import OllamaLLM

class ModelRouter:

    def __init__(self):
        self.primary = OllamaLLM()
        self.fallback = GeminiLLM()

    def generate(self, prompt):

        try:
            return self.primary.generate(prompt)

        except Exception:
            result = self.fallback.generate(prompt)
            result["fallback"] = True   # flag that gemini was used
            return result