import re
from typing import Optional


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)[\d .-]{8,13}\d(?!\d)")


def redact_pii(value: Optional[str]) -> str:
    """Redact common contact PII before logging, tracing or prompt enrichment."""
    text = value or ""
    text = EMAIL_RE.sub("[EMAIL_REDACTED]", text)
    return PHONE_RE.sub("[PHONE_REDACTED]", text)


def mask_phone(value: Optional[str]) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 4:
        return "***"
    return f"***{digits[-3:]}"
