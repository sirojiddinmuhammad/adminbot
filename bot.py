import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import ADMIN_ID, BOT_TOKEN
from handlers import router
from hisobot import router as hisobot_router
from ustozlar import router as ustozlar_router
from kk import router as kk_router
from talaba_holati import router as talaba_holati_router

logging.basicConfig(level=logging.INFO)


async def _buyruqlar_menyusini_ornat(bot: Bot) -> None:
    """Telegram'ning "☰ Menyu" ro'yxatiga buyruqlarni chiqaradi."""
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Botni ishga tushirish"),
        ]
    )


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Faqat admin ishlata oladi
    router.message.filter(F.from_user.id == ADMIN_ID)
    router.callback_query.filter(F.from_user.id == ADMIN_ID)
    hisobot_router.message.filter(F.from_user.id == ADMIN_ID)
    hisobot_router.callback_query.filter(F.from_user.id == ADMIN_ID)
    ustozlar_router.message.filter(F.from_user.id == ADMIN_ID)
    ustozlar_router.callback_query.filter(F.from_user.id == ADMIN_ID)

    talaba_holati_router.message.filter(F.from_user.id == ADMIN_ID)
    talaba_holati_router.callback_query.filter(F.from_user.id == ADMIN_ID)

    # talaba_holati birinchi ulanadi: "🎓 Talaba holati" tugmasi boshqa oqim
    # (masalan Yangi talaba) o'rtasida bosilsa ham ishlashi uchun
    dp.include_router(talaba_holati_router)
    dp.include_router(router)
    dp.include_router(hisobot_router)
    dp.include_router(ustozlar_router)
    # kk_router'ga ADMIN_ID filtri qo'yilmaydi: admin bo'lmaganlarga
    # "Ruxsat yo'q" javobi handler ichida beriladi
    dp.include_router(kk_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await _buyruqlar_menyusini_ornat(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
