import logging
import re


REDACTION_RULES = (
    (re.compile(r'(/confirmar-email/)[^/?\s]+', re.IGNORECASE), r'\1[redacted]'),
    (
        re.compile(r'([?&](?:token|key|secret)=)[^&\s]+', re.IGNORECASE),
        r'\1[redacted]',
    ),
    (re.compile(r'(bearer\s+)[a-z0-9._~-]+', re.IGNORECASE), r'\1[redacted]'),
    (
        re.compile(
            r'(?<!\d)(?:\d{3}\.?\d{3}\.?\d{3}-?\d{2}|'
            r'\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)'
        ),
        '[document-redacted]',
    ),
    (
        re.compile(r'(?<![\w.+-])[\w.+-]+@[\w.-]+\.[a-z]{2,}(?![\w.-])', re.IGNORECASE),
        '[email-redacted]',
    ),
)


def redact_sensitive_log_data(message):
    redacted = str(message)
    for pattern, replacement in REDACTION_RULES:
        redacted = pattern.sub(replacement, redacted)
    return redacted[:2000]


class RedactingFormatter(logging.Formatter):
    """Redact secrets and identifiers after formatting, including tracebacks."""

    def format(self, record):
        return redact_sensitive_log_data(super().format(record))
