import os
from google import genai
from .base_llm import BaseLLM
import time

class GeminiLLM(BaseLLM):

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def generate(self, prompt: str) :

        start = time.time()
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        latency_ms = round((time.time() - start) * 1000)
        usage = response.usage_metadata  # Gemini's native usage object
    
        print("Model Name:", self.model_name)
        print("env model:", os.getenv("GEMINI_MODEL"))
        
        return {
            "text":           response.text,
            "model":          self.model_name,
            "provider":       "gemini",
            "input_tokens":   usage.prompt_token_count,
            "output_tokens":  usage.candidates_token_count,
            "total_tokens":   usage.total_token_count,
            "latency_ms":     latency_ms,
            "context_window": usage.prompt_token_count,
        }