def safe_text_sample(text: str, limit: int = 300) -> str:
    """Return a bounded-length sample for logging."""
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "…"
