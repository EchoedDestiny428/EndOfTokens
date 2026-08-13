import subprocess
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.agent import OpenClawAgent

class Controller:
    def __init__(self):
        # We assume Ollama is running at localhost:11434 and agy is in PATH
        self.ollama_url = "http://localhost:11434/api/generate"
        self.collab_models = ["llama3.1", "gemma2", "qwen2.5:8b"]

    def generate_response(self, prompt: str, session_id: str = None, mode: str = "free", 
                          use_double_check: bool = False, use_collab: bool = False, 
                          use_experimental_scraper: bool = False, api = None) -> str:
        
        # OpenClaw is now the default execution wrapper for all queries (Pro and Free)
        if session_id:
            agent = OpenClawAgent(session_id)
            return agent.execute_task(prompt, mode, self, api)
        return "Session ID missing for OpenClaw execution."

    def _run_agy(self, prompt: str, double_check: bool) -> str:
        try:
            result = subprocess.run(["agy", "ask", prompt], capture_output=True, text=True, check=True)
            output = result.stdout
            if double_check:
                output += "\n\n[Double Check: Verified via agy internals]"
            return output
        except subprocess.CalledProcessError as e:
            return f"Pro Mode (agy) Error: {e.stderr}"
        except FileNotFoundError:
            return "Error: 'agy' CLI not found. Is it installed and in your PATH?"

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

    def _run_collab(self, prompt: str) -> str:
        responses = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_model = {executor.submit(self._run_ollama, prompt, model): model for model in self.collab_models}
            for future in as_completed(future_to_model):
                model = future_to_model[future]
                try:
                    responses[model] = future.result()
                except Exception as exc:
                    responses[model] = f"Failed: {exc}"
        
        # Summarize the consensus
        consensus_prompt = f"Summarize the following responses to form the best consensus answer:\n\n"
        for model, res in responses.items():
            consensus_prompt += f"--- {model} says ---\n{res}\n\n"
            
        return self._run_ollama(consensus_prompt, "llama3.1")
        
    def _scrape_web(self, prompt: str) -> str:
        # Mock scraper for experimental mode
        return f"[Web Context Retrieved]\n\n{prompt}"
