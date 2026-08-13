import webview
import threading
import time
import requests
import subprocess
import json
from core.controller import Controller
from core.session_manager import session_manager

class Api:
    def __init__(self):
        self.controller = Controller()
        self.approval_event = threading.Event()
        self.approval_result = False

    def request_approval(self, command: str, reason: str) -> bool:
        self.approval_event.clear()
        # Escape for JS
        cmd_escaped = json.dumps(command)
        reason_escaped = json.dumps(reason)
        webview.windows[0].evaluate_js(f'showApprovalModal({cmd_escaped}, {reason_escaped})')
        self.approval_event.wait()
        return self.approval_result

    def resolve_approval(self, approved: bool):
        self.approval_result = approved
        self.approval_event.set()

    def create_session(self, title: str):
        session = session_manager.create_session(title)
        return session.to_dict()

    def get_all_sessions(self):
        return session_manager.get_all_sessions()

    def get_session(self, session_id: str):
        session = session_manager.get_session(session_id)
        return session.to_dict() if session else None

    def rename_session(self, session_id: str, new_title: str):
        session_manager.rename_session(session_id, new_title)
        return True

    def delete_session(self, session_id: str):
        session_manager.delete_session(session_id)
        return True

    def update_session_settings(self, session_id: str, settings: dict):
        session = session_manager.get_session(session_id)
        if session:
            session.update_settings(settings)
            session_manager.save()
            return True
        return False

    def open_dashboard(self):
        # Open a completely separate popup window for the dashboard
        webview.create_window(
            title='Global Dashboard', 
            url='web/dashboard.html', 
            width=400, 
            height=500,
            background_color='#000000',
            js_api=self
        )
        return True

    def generate_response(self, session_id: str, prompt: str, mode: str, use_dc: bool, use_collab: bool, use_exp: bool):
        session = session_manager.get_session(session_id)
        if not session:
            raise Exception("Session not found")

        if session.title == "New Task":
            session.title = (prompt[:30] + '...') if len(prompt) > 30 else prompt

        session.add_message("user", prompt)
        session_manager.save()

        start_time = time.time()
        
        response_text = self.controller.generate_response(
            session_id=session_id,
            prompt=prompt,
            mode=mode,
            use_double_check=use_dc,
            use_collab=use_collab,
            use_experimental_scraper=use_exp,
            api=self
        )
        
        elapsed_time = time.time() - start_time

        session.add_message("assistant", response_text)
        session.update_stats(mode, use_collab, True, elapsed_time)
        session_manager.save()

        return {
            "content": response_text,
            "session": session.to_dict()
        }

def ensure_ollama_running():
    try:
        requests.get("http://localhost:11434", timeout=2)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        try:
            subprocess.Popen(
                ["ollama", "serve"], 
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(3)
        except Exception:
            pass

if __name__ == '__main__':
    threading.Thread(target=ensure_ollama_running, daemon=True).start()
    
    api = Api()
    webview.create_window(
        title='End Of Tokens (Agent UI)', 
        url='web/index.html', 
        js_api=api,
        width=1000, 
        height=700,
        background_color='#000000'
    )
    webview.start()
