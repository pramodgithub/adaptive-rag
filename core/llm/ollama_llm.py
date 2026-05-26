import requests
from .base_llm import BaseLLM
from .ollama_config import OLLAMA_CONFIG, LLM_MODE
import time


class OllamaLLM(BaseLLM):

    def __init__(self, mode: str = LLM_MODE):
        self.mode = mode
        self.config = OLLAMA_CONFIG[mode]
        self.base_url = self.config["base_url"]
        self.model = self.config["model"]

        # Only cloud needs auth header
        self.headers = {"Content-Type": "application/json"}
        if self.mode == "cloud":
            api_key = self.config.get("api_key")
            if not api_key:
                raise ValueError("OLLAMA_API_KEY is not set for cloud mode")
            self.headers["Authorization"] = f"Bearer {api_key}"

    def generate(self, prompt: str):

        start = time.time()
        response = requests.post(
            f"{self.base_url}/api/generate",
            headers=self.headers,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False         # set True if you want streaming
            }
        )
        response.raise_for_status()     # raises error on bad status codes
        latency_ms = round((time.time() - start) * 1000)

        data = response.json()

        return {
            "text":  data["response"],
            "model": self.model,
            "provider": "ollama",
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            "latency_ms": latency_ms,
            "context_window": data.get("prompt_eval_count", 0)
        }
