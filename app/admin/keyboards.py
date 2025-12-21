from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Проверить взносы")],
            [KeyboardButton(text="Обращения"), KeyboardButton(text="Заявления")],
            [KeyboardButton(text="Отчеты")],
            [KeyboardButton(text="Индивидуальная рассылка")]
        ],
        resize_keyboard=True
    )

def application_review_keyboard(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"app_approve_{app_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"app_reject_{app_id}")
            ]
        ]
    )

def appeal_answer_keyboard(appeal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✉️ Ответить", callback_data=f"appeal_reply_{appeal_id}")
            ]
        ]
    )

def fee_check_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"fee_approve_{payment_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"fee_reject_{payment_id}")
            ]
        ]
    )
