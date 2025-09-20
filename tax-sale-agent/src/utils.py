import re
from typing import Optional, Tuple

MONEY_RE = re.compile(r"[^\d.\-]")
ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")

def parse_money(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    try:
        cleaned = MONEY_RE.sub("", str(text))
        return float(cleaned) if cleaned else None
    except Exception:
        return None

def normalize_zip(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = ZIP_RE.search(text)
    return m.group(1) if m else None

def split_city_state_zip(blob: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not blob:
        return (None, None, None)
    import re as _re
    m = _re.match(r"\s*(.*?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)", blob.strip())
    if m:
        from .utils import normalize_zip as _nz
        return (m.group(1), m.group(2), _nz(m.group(3)))
    return (None, None, normalize_zip(blob))
