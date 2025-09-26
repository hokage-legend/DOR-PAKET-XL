import json
import os
from typing import Dict

class BalanceService:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.filepath = "user_balances.json"
            self.balances: Dict[str, float] = {}
            self._load_balances()
            self.initialized = True
            print("BalanceService (berbasis chat_id) Initialized.")

    def _load_balances(self):
        """Memuat data saldo dari file JSON."""
        if not os.path.exists(self.filepath):
            self._save_balances()
        
        with open(self.filepath, 'r', encoding='utf-8') as f:
            try:
                # Kunci di JSON adalah string, jadi tidak masalah
                self.balances = json.load(f)
            except json.JSONDecodeError:
                self.balances = {}

    def _save_balances(self):
        """Menyimpan data saldo ke file JSON."""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.balances, f, indent=4)

    def get_balance(self, chat_id: int) -> float:
        """Mendapatkan saldo berdasarkan chat_id. Mengembalikan 0 jika tidak ada."""
        return self.balances.get(str(chat_id), 0.0)

    def add_balance(self, chat_id: int, amount: float) -> float:
        """Menambah saldo untuk pengguna (untuk top up)."""
        current_balance = self.get_balance(chat_id)
        new_balance = current_balance + amount
        self.balances[str(chat_id)] = new_balance
        self._save_balances()
        print(f"Saldo untuk chat_id {chat_id} ditambahkan sebesar {amount}. Saldo baru: {new_balance}")
        return new_balance

    def deduct_balance(self, chat_id: int, amount: float) -> bool:
        """Memotong saldo pengguna (untuk biaya transaksi)."""
        current_balance = self.get_balance(chat_id)
        if current_balance < amount:
            print(f"Gagal memotong saldo chat_id {chat_id}. Saldo tidak cukup.")
            return False
        
        new_balance = current_balance - amount
        self.balances[str(chat_id)] = new_balance
        self._save_balances()
        print(f"Saldo untuk chat_id {chat_id} dipotong sebesar {amount}. Saldo baru: {new_balance}")
        return True

BalanceServiceInstance = BalanceService()