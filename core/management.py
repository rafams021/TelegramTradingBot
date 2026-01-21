import re
from typing import Optional, Tuple

# Ejemplos:
# "CERRAR AHORA A 4856"
# "CERRAR A 4850"
_re_close_at = re.compile(r"\bCERRAR\b(?:\s+AHORA)?\s+\bA\b\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def classify_management(text: str) -> Tuple[Optional[str], Optional[float]]:
    """
    Returns: (kind, price)
      kind in {"BE", "CLOSE", "CLOSE_AT"} o (None, None)
    """
    t = (text or "").strip()
    if not t:
        return None, None

    up = t.upper()

    # BE: cualquier mensaje que contenga "BE"
    if "BE" in up:
        return "BE", None

    m = _re_close_at.search(t)
    if m:
        try:
            return "CLOSE_AT", float(m.group(1))
        except ValueError:
            return None, None

    if "CERRAR" in up:
        return "CLOSE", None

    return None, None

