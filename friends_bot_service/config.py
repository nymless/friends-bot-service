import logging
import sys
from os import getenv

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

load_dotenv()

_token = getenv("BOT_TOKEN")
_path = getenv("DB_PATH")
_chat_id = getenv("ALLOWED_CHAT_ID")

if not (_token and _path and _chat_id):
    logger.error("Отсутствует .env файл или определены не все локальные переменные.")
    sys.exit(1)

BOT_TOKEN: str = _token
DB_PATH: str = _path
ALLOWED_CHAT_ID: int = int(_chat_id)
ALLOWED_CHAT_TYPES: set[str] = {"group", "supergroup"}
