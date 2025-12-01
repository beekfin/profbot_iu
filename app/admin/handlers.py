from aiogram import Router, types, F
from aiogram.filters import Command

from app.database import db
from app.logger import logger


router = Router(name="admin")


@router.message(Command("admin"))
@router.message(F.text == "Админ панель")
async def admin_entrypoint(message: types.Message) -> None:
    """Simple entrypoint that checks access to admin-only features."""
    telegram_id = message.from_user.id

    try:
        if not await _user_is_admin(telegram_id):
            await message.answer("⛔️ Доступ запрещён. Режим администратора доступен только сотрудникам профкома.")
            return

        await message.answer(
            "🔐 Добро пожаловать в административный режим.\n"
            "Пока что общие функции находятся в студенческом меню, но сюда будут добавлены отдельные команды.",
        )
    except Exception as exc:
        logger.error(f"Ошибка входа в админ-панель: {exc}")
        await message.answer("Не удалось открыть админ-панель. Попробуйте позже.")


async def _user_is_admin(telegram_id: int) -> bool:
    """Return True if user has role admin."""
    try:
        row = await db.fetchrow(
            f"""
            SELECT 1
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE u.telegram_id = {int(telegram_id)} AND r.code = 'admin'
            """
        )
        return row is not None
    except Exception as exc:
        logger.error(f"Не удалось проверить права администратора: {exc}")
        return False
