import json
from datetime import datetime, timezone
from typing import Dict, Any
from config import LOG_FILE

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def log(ev: Dict[str, Any]) -> None:
    e = dict(ev)
    e["ts"] = e.get("ts") or now_iso()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
