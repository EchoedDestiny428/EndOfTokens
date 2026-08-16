import uuid
import time
import json
import os
from typing import Dict, List

class TaskSession:
    def __init__(self, title="New Task"):
        self.id = str(uuid.uuid4())
        self.title = title
        self.history: List[Dict] = []
        self.plan: List[Dict] = []
        self.local_storage: Dict = {}
        self.thought_process: str = ""
        self.stats = {
            "total_requests": 0,
            "total_time": 0.0,
            "pro_uses": 0,
            "free_uses": 0,
            "collab_uses": 0,
            "openclaw_uses": 0
        }
        self.settings = {
            "pro_mode": False,
            "collab_mode": False,
            "double_check": False,
            "exp_scraper": False,
            "turbo_mode": False,
            "persistence_mode": False
        }
        self.created_at = time.time()

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def update_stats(self, mode: str, elapsed_time: float):
        self.stats["total_requests"] += 1
        self.stats["total_time"] += elapsed_time
        if mode == "pro":
            self.stats["pro_uses"] += 1
        else:
            self.stats["free_uses"] += 1
        self.stats["openclaw_uses"] += 1

    def update_settings(self, settings_dict: Dict):
        self.settings.update(settings_dict)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "history": self.history,
            "plan": self.plan,
            "local_storage": self.local_storage,
            "thought_process": self.thought_process,
            "stats": self.stats,
            "settings": self.settings,
            "created_at": self.created_at
        }
        
    @classmethod
    def from_dict(cls, data: Dict):
        session = cls()
        session.id = data.get("id", session.id)
        session.title = data.get("title", "New Task")
        session.history = data.get("history", [])
        session.plan = data.get("plan", [])
        session.local_storage = data.get("local_storage", {})
        session.thought_process = data.get("thought_process", "")
        session.stats = data.get("stats", session.stats)
        session.settings = data.get("settings", session.settings)
        session.created_at = data.get("created_at", session.created_at)
        return session

class SessionManager:
    def __init__(self, db_path="sessions.json"):
        self.db_path = db_path
        self.sessions: Dict[str, TaskSession] = {}
        self.load()

    def load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for s_data in data:
                        session = TaskSession.from_dict(s_data)
                        self.sessions[session.id] = session
            except Exception as e:
                print(f"Failed to load sessions: {e}")

    def save(self):
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in self.sessions.values()], f, indent=4)
        except Exception as e:
            print(f"Failed to save sessions: {e}")

    def create_session(self, title="New Task") -> TaskSession:
        session = TaskSession(title)
        self.sessions[session.id] = session
        self.save()
        return session

    def get_session(self, session_id: str) -> TaskSession:
        return self.sessions.get(session_id)

    def rename_session(self, session_id: str, new_title: str):
        if session_id in self.sessions:
            self.sessions[session_id].title = new_title
            self.save()

    def delete_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            self.save()

    def get_all_sessions(self) -> List[Dict]:
        return [s.to_dict() for s in sorted(self.sessions.values(), key=lambda x: x.created_at, reverse=True)]

session_manager = SessionManager()

class GlobalStorageManager:
    def __init__(self, db_path="global_storage.json"):
        self.db_path = db_path
        self.storage: Dict[str, Dict[str, str]] = {}
        self.load()

    def load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self.storage = json.load(f)
            except Exception as e:
                print(f"Failed to load global storage: {e}")

    def save(self):
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.storage, f, indent=4)
        except Exception as e:
            print(f"Failed to save global storage: {e}")

    def set(self, category: str, key: str, value: str):
        if category not in self.storage:
            self.storage[category] = {}
        self.storage[category][key] = value
        self.save()

    def get(self, category: str, key: str) -> str:
        return self.storage.get(category, {}).get(key, None)

    def get_toc(self) -> Dict[str, List[str]]:
        toc = {}
        for category, keys in self.storage.items():
            toc[category] = list(keys.keys())
        return toc

global_storage_manager = GlobalStorageManager()
