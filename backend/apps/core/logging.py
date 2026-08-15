import logging

_SENSITIVE = (
    "HTTP_AUTHORIZATION",
    "HTTP_X_TABLIO_APP_KEY",
    "Authorization",
    "X-Tablio-App-Key",
)


class SensitiveHeaderFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = str(record.getMessage())
        for key in _SENSITIVE:
            if key.lower() in message.lower():
                record.msg = "[redacted sensitive header]"
                record.args = ()
                break
        if hasattr(record, "request"):
            meta = getattr(record.request, "META", None)
            if isinstance(meta, dict):
                for key in ("HTTP_AUTHORIZATION", "HTTP_X_TABLIO_APP_KEY"):
                    if key in meta:
                        meta[key] = "[redacted]"
        return True
