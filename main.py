import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import TELEGRAM_TOKEN
from handlers import router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


async def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is not configured.")

    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    logger.info("Telegram invoice bot started.")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
