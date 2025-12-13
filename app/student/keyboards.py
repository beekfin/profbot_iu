from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="Расписание"),
            KeyboardButton(text="Карта"),
        ],
        [
            KeyboardButton(text="Профиль"),
        ],
        [
            KeyboardButton(text="Подать заявление"),
        ],
        [
            KeyboardButton(text="Статус заявления"),
            KeyboardButton(text="Статус профвзноса"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )


def confirm_keyboard(allow_edit: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="✅ Подтвердить данные",
                callback_data="confirm_profile",
            )
        ]
    ]

    if allow_edit:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✏ Перезаполнить данные",
                    callback_data="edit_profile",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)
