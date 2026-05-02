import logging
from datetime import datetime

RESET = "\033[0m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
GREEN = "\033[92m"
BOLD = "\033[1m"


class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: CYAN,
        logging.INFO: CYAN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED + BOLD,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, RESET)
        ts = datetime.now().strftime("%d.%m.%Y  %H:%M:%S")
        return f"{color}{ts}  {record.getMessage()}{RESET}"


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("trendox")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(ColorFormatter())
        logger.addHandler(handler)

    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    return logger


log = setup_logger()
