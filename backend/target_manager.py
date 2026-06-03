import uuid
from datetime import datetime
from typing import List, Dict


class TargetManager:
    def __init__(self):
        self._targets: Dict[str, dict] = {}

    def add_target(
        self,
        symbol: str,
        target_price: float,
        target_type: str = "above",
        note: str = "",
    ) -> dict:
        tid = str(uuid.uuid4())[:8]
        target = {
            "id": tid,
            "symbol": symbol.upper(),
            "target_price": target_price,
            "target_type": target_type,  # "above" or "below"
            "note": note,
            "created_at": datetime.now().isoformat(),
        }
        self._targets[tid] = target
        return target

    def remove_target(self, target_id: str) -> dict:
        return self._targets.pop(target_id, {})

    def get_all(self) -> List[dict]:
        return list(self._targets.values())

    def check_targets(self, quotes: Dict[str, dict]) -> List[dict]:
        triggered = []
        to_remove = []

        for tid, target in self._targets.items():
            symbol = target["symbol"]
            price = quotes.get(symbol, {}).get("price", 0)
            if not price:
                continue

            hit = (
                (target["target_type"] == "above" and price >= target["target_price"]) or
                (target["target_type"] == "below" and price <= target["target_price"])
            )

            if hit:
                triggered.append({**target, "current_price": price})
                to_remove.append(tid)

        for tid in to_remove:
            del self._targets[tid]

        return triggered
