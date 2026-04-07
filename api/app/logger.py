import logging
import os
from contextvars import ContextVar

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s [%(request_id)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

for _handler in logging.getLogger().handlers:
    _handler.addFilter(_RequestIdFilter())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
