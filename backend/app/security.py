import re


def sanitize_secret(text: str | None, secret: str | None = None) -> str:
    if not text:
        return ""

    safe = str(text)

    if secret:
        safe = safe.replace(secret, "[REDACTED]")

    # Alpha Vantage commonly phrases rate-limit messages like:
    # "We have detected your API key as ABC123..."
    safe = re.sub(
        r"(?i)(api\s+key\s+(?:is|as)\s+)([A-Za-z0-9_-]{6,})",
        r"\1[REDACTED]",
        safe,
    )

    # Also redact common query-string forms.
    safe = re.sub(
        r"(?i)(apikey=)([^&\s]+)",
        r"\1[REDACTED]",
        safe,
    )

    return safe
