import os
import json
import time
from datetime import datetime
from app.client.engsel import get_new_token
from app.util import ensure_api_key

class Auth:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.api_key = ensure_api_key()
            self.tokens_filepath = "refresh-tokens.json"
            self.sessions_filepath = "sessions.json"
            
            self.refresh_tokens = self._load_from_json(self.tokens_filepath, [])
            self.active_users = {}
            self.impersonation_map = {} # Untuk menyimpan sesi asli admin
            
            self._load_and_restore_sessions()
            
            self.initialized = True
            print("AuthService (Multi-User dengan Ingatan & Admin) Initialized.")

    def _load_from_json(self, filepath: str, default_value):
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(default_value, f)
            return default_value
        with open(filepath, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return default_value

    def _save_to_json(self, filepath: str, data):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _load_and_restore_sessions(self):
        sessions = self._load_from_json(self.sessions_filepath, {})
        if not sessions: return
        print(f"Memulihkan {len(sessions)} sesi dari file...")
        for chat_id_str, number in sessions.items():
            chat_id = int(chat_id_str)
            self.set_active_user(chat_id, number)

    def add_refresh_token(self, number: int, refresh_token: str, chat_id: int, username: str):
        number_found = False
        registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for i, token_entry in enumerate(self.refresh_tokens):
            if token_entry.get("number") == number:
                self.refresh_tokens[i]['refresh_token'] = refresh_token
                self.refresh_tokens[i]['chat_id'] = chat_id
                self.refresh_tokens[i]['username'] = username if username else "N/A"
                if 'registration_date' not in token_entry or not token_entry['registration_date']:
                    self.refresh_tokens[i]['registration_date'] = registration_date
                number_found = True
                break
        if not number_found:
            self.refresh_tokens.append({
                "number": number, "refresh_token": refresh_token, "chat_id": chat_id,
                "username": username if username else "N/A", "registration_date": registration_date
            })
        self._save_to_json(self.tokens_filepath, self.refresh_tokens)

    def set_active_user(self, chat_id: int, number: int):
        rt_entry = next((rt for rt in self.refresh_tokens if rt.get("number") == number), None)
        if not rt_entry: return False
        tokens = get_new_token(rt_entry.get("refresh_token"))
        if not tokens: return False
        self.active_users[chat_id] = {"number": int(number), "tokens": tokens, "last_refresh": int(time.time())}
        sessions = self._load_from_json(self.sessions_filepath, {})
        sessions[str(chat_id)] = number
        self._save_to_json(self.sessions_filepath, sessions)
        print(f"Sesi aktif dibuat/diperbarui untuk chat_id {chat_id} dengan nomor {number}")
        return True

    def get_active_user(self, chat_id: int):
        if chat_id in self.impersonation_map:
            impersonated_chat_id = self.impersonation_map[chat_id]
            return self.get_active_user(impersonated_chat_id)
        user_session = self.active_users.get(chat_id)
        if not user_session: return None
        if (int(time.time()) - user_session.get("last_refresh", 0)) > 300:
            print(f"Memperbarui token untuk chat_id {chat_id}...")
            # ... (logika refresh token)
        return user_session

    def logout(self, chat_id: int):
        if chat_id in self.active_users: del self.active_users[chat_id]
        sessions = self._load_from_json(self.sessions_filepath, {})
        if str(chat_id) in sessions:
            del sessions[str(chat_id)]
            self._save_to_json(self.sessions_filepath, sessions)
        print(f"Sesi untuk chat_id {chat_id} telah dihapus (logout).")

    def get_all_registered_users(self):
        return self.refresh_tokens

    def start_impersonation(self, admin_chat_id: int, target_user_number: int):
        target_user_data = next((user for user in self.refresh_tokens if user.get("number") == target_user_number), None)
        if not target_user_data or not target_user_data.get("chat_id"):
            return f"Error: Pengguna dengan nomor {target_user_number} tidak terdaftar."
        target_chat_id = target_user_data["chat_id"]
        if not self.active_users.get(target_chat_id):
            if not self.set_active_user(target_chat_id, target_user_number):
                return f"Gagal membuat sesi untuk pengguna {target_user_number}."
        self.impersonation_map[admin_chat_id] = target_chat_id
        return f"Anda sekarang bertindak sebagai pengguna {target_user_number}."

    def stop_impersonation(self, admin_chat_id: int):
        if admin_chat_id in self.impersonation_map:
            del self.impersonation_map[admin_chat_id]
            return "Anda telah kembali ke akun admin Anda."
        return "Anda tidak sedang menyamar."

AuthInstance = Auth()