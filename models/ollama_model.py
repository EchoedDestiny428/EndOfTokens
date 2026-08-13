import requests
import json
from models.base_model import BaseModel

class OllamaModel(BaseModel):
    def __init__(self, model_name: str = "llama3.1"):
        super().__init__()
        self.model_name = model_name
        self.api_url = "http://localhost:11434/api/generate"
        
    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.exceptions.ConnectionError:
            return f"Error: Could not connect to Ollama. Make sure Ollama is running."
        except Exception as e:
            return f"Error communicating with Ollama ({self.model_name}): {str(e)}"
