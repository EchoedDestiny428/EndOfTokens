import subprocess
from models.base_model import BaseModel

class ProModel(BaseModel):
    def __init__(self):
        super().__init__()
        
    def generate(self, prompt: str) -> str:
        try:
            # Assuming agy takes the prompt as an argument or from stdin
            # Here we pass it as a positional argument: agy "prompt"
            # Or perhaps: agy prompt "prompt" 
            # We'll use the simplest invocation, assuming `agy` can read from args
            result = subprocess.run(
                ["agy", prompt],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error executing Pro model (agy CLI): {e.stderr}"
        except FileNotFoundError:
            return "Error: 'agy' command not found. Ensure it is installed and in your PATH."
        except Exception as e:
            return f"Unexpected error: {str(e)}"
