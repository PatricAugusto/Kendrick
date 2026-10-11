import logging
import traceback


class SecretRedactionFilter(logging.Filter):
    def __init__(self, secret: str) -> None:
        super().__init__()
        self._secret = secret

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        traceback_text = ""
        if record.exc_info is not None:
            traceback_text = "".join(traceback.format_exception(*record.exc_info))

        if self._secret in message or self._secret in traceback_text:
            record.msg = message.replace(self._secret, "[REDACTED]")
            record.args = ()
            record.exc_info = None
            record.exc_text = None

        return True


def configure_logging(token: str) -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    root_logger = logging.getLogger()
    redaction_filter = SecretRedactionFilter(token)
    for handler in root_logger.handlers:
        handler.addFilter(redaction_filter)

    logging.getLogger("httpx").setLevel(logging.WARNING)
