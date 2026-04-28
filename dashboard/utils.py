import logging
import re
import time
from datetime import datetime, timezone

logger = logging.getLogger("pr_dashboard")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_date(s):
    if not s or not _DATE_RE.match(s):
        raise ValueError(f"Fecha inválida: {s!r}. Formato esperado: YYYY-MM-DD")
    datetime.strptime(s, "%Y-%m-%d")
    return s


def minutes_between(a, b):
    if not a or not b:
        return ""
    def parse(s):
        s = s.rstrip("Z")
        if "+" in s:
            s = s[:s.index("+")]
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    try:
        return round((parse(b) - parse(a)).total_seconds() / 60)
    except Exception:
        return ""


def retry(fn, retries=2, base_delay=0.5, label=""):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                logger.error("[retry:%s] Falló tras %d intentos: %s", label, retries, e)
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning("[retry:%s] Intento %d/%d falló (%s). Reintentando en %.1fs...",
                           label, attempt + 1, retries, e, delay)
            time.sleep(delay)
