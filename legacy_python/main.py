import customtkinter as ctk
import subprocess
import requests
import threading
import time
from gui.main_window import MainWindow

def ensure_ollama_running():
    """Checks if Ollama is running, and starts it in the background if it's not."""
    try:
        # Check if Ollama API is responsive
        requests.get("http://localhost:11434", timeout=2)
        print("Ollama is already running.")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        print("Ollama is not running. Starting it in the background...")
        try:
            # Launch ollama serve in the background
            # creationflags=subprocess.CREATE_NO_WINDOW prevents a black cmd box from popping up on Windows
            subprocess.Popen(
                ["ollama", "serve"], 
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Give it a few seconds to fully spin up before the GUI loads
            time.sleep(3) 
            print("Ollama background service started!")
        except FileNotFoundError:
            print("Warning: 'ollama' command not found. Ensure it is installed and in your PATH.")
        except Exception as e:
            print(f"Warning: Failed to start Ollama automatically: {e}")

if __name__ == "__main__":
    # Start Ollama automatically in the background so the user doesn't have to!
    threading.Thread(target=ensure_ollama_running, daemon=True).start()

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    app = MainWindow()
    app.mainloop()
