import os
import json
import time
from typing import Dict, Any, Optional

class QuotaManager:
    _instance = None
    
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), "../../../data/quotas.json")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.data = self._load_data()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_data(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_balance(self, user_id: str, rank: str = "Ensign") -> int:
        user_id = str(user_id)
        self._check_daily_allowance(user_id, rank)
        return self.data.get(user_id, {}).get("balance", 0)

    def spend_credits(self, user_id: str, amount: int) -> bool:
        user_id = str(user_id)
        current_balance = self.get_balance(user_id)
        if current_balance < amount:
            return False
            
        self.data[user_id]["balance"] -= amount
        self._save_data()
        return True

    def add_credits(self, user_id: str, amount: int):
        user_id = str(user_id)
        if user_id not in self.data:
            self.data[user_id] = {"balance": 0, "last_allowance": 0}
        self.data[user_id]["balance"] += amount
        self._save_data()

    def _check_daily_allowance(self, user_id: str, rank: str):
        now = int(time.time())
        one_day = 86400
        
        if user_id not in self.data:
            self.data[user_id] = {"balance": 0, "last_allowance": 0}
            
        user_data = self.data[user_id]
        last_allowance = user_data.get("last_allowance", 0)
        
        if now - last_allowance >= one_day:
            allowance = self._get_rank_allowance(rank)
            user_data["balance"] += allowance
            user_data["last_allowance"] = now
            self._save_data()

    def _get_rank_allowance(self, rank: str) -> int:
        # Rank-based daily credits
        rank_map = {
            "Fleet Admiral": 1000,
            "Admiral": 800,
            "Vice Admiral": 700,
            "Rear Admiral": 600,
            "Commodore": 500,
            "Captain": 400,
            "Commander": 300,
            "Lt. Commander": 250,
            "Lieutenant": 200,
            "Lieutenant J.G.": 150,
            "Ensign": 100,
            "Crewman": 50,
            "Civilian": 20
        }
        return rank_map.get(rank, 100)

# Helper function
def get_quota_manager():
    return QuotaManager.get_instance()
