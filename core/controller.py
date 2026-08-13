import requests
import json
from core.agent import OpenClawAgent

class Controller:
    def __init__(self):
        # We assume Ollama is running at localhost:11434
        self.ollama_url = "http://localhost:11434/api/generate"

    def generate_response(self, prompt: str, session_id: str = None, mode: str = "free", 
                          use_double_check: bool = False, use_collab: bool = False, 
                          use_experimental_scraper: bool = False, api = None) -> str:
        
        # End Of Tokens is the default execution wrapper for all queries
        if session_id:
            agent = OpenClawAgent(session_id)
            return agent.execute_task(prompt, mode, self, api)
        return "Session ID missing for execution."

    def _run_ollama(self, prompt: str, model: str) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            return f"Ollama Local Error ({model}): {str(e)}"
