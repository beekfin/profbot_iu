from os import getenv
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.handlers import router 
from app.logger import logger
from app.database import db


load_dotenv()
API_TOKEN = getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("Не найден API_TOKEN в переменных окружения")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

dp.include_router(router)


from app.database import db

async def start_bot():
    logger.info("Подключение к базе данных...")
    await db.connect()

    logger.info("Starting bot...")
    await dp.start_polling(bot)

    logger.info("Закрытие соединения с БД...")
    await db.close()
