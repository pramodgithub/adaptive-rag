import os

# Switch between "local" and "cloud"
LLM_MODE = os.getenv("LLM_MODE", "local")

OLLAMA_CONFIG = {
    "local": {
        "base_url": "http://localhost:11434",
        "model": "qwen2.5:1.5b",          # your local model
    },
    "cloud": {
        "base_url": "https://api.ollama.com",  # Ollama cloud endpoint
        "model": "qwen3-coder:480b-cloud",
        "api_key": os.getenv("OLLAMA_API_KEY", ""),  # set in .env
    }
}