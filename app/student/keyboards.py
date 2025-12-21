from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="Профиль"),
        ],
        [
            KeyboardButton(text="Расписание"),
            KeyboardButton(text="Карта"),
        ],
        [
            KeyboardButton(text="Подать заявление"),
            KeyboardButton(text="Написать обращение")
        ],
        [
            KeyboardButton(text="Статус заявления"),
            KeyboardButton(text="Статус профвзноса"),
        ],
        [
            KeyboardButton(text="Мероприятия"),
            KeyboardButton(text="Новости"),
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )


def applications_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="Скачать бланк"),
            KeyboardButton(text="Загрузить заявление"),
        ],
        [
            KeyboardButton(text="Назад"),
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def application_templates_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Материальная помощь", callback_data="tpl_material_aid")
            ]
        ]
    )


def material_aid_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Единовременная мат.поддержка", callback_data="ma_type_one_time")],
            [InlineKeyboardButton(text="Компенсация проезда", callback_data="ma_type_travel")],
            [InlineKeyboardButton(text="Компенсация проживания", callback_data="ma_type_dorm")],
            [InlineKeyboardButton(text="Отмена", callback_data="ma_cancel")]
        ]
    )


def material_aid_travel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="До места жительства", callback_data="ma_travel_home")],
            [InlineKeyboardButton(text="До места лечения", callback_data="ma_travel_treatment")],
            [InlineKeyboardButton(text="Назад", callback_data="ma_back_to_type")]
        ]
    )


MATERIAL_AID_CATEGORIES = {
    "category_orphan": "Сирота",
    "category_disabled": "Инвалид",
    "category_disabled_war_trauma": "Инвалид (военная травма)",
    "category_chernobyl": "Чернобылец",
    "category_veteran": "Ветеран БД",
    "category_family_injured_svo": "Семья СВО (увечье)",
    "category_family_killed_svo": "Семья СВО",
    "category_hero_rf": "Герой РФ",
    "category_single_parent": "Одинокий родитель",
    "category_young_family_with_kids": "Молодая семья с детьми",
    "category_children_disabled": "Дети-инвалиды",
    "category_young_family": "Молодая семья",
    "category_pregnancy": "Беременность",
    "category_incomplete_family": "Неполная семья",
    "category_large_family": "Многодетная семья",
    "category_parent_disabled": "Родитель-инвалид",
    "category_parent_pensioner": "Родитель-пенсионер",
    "category_dispanser": "Диспансерный учет",
    "category_donor": "Донор",
    "category_nonresident_no_dorm": "Иногородний (без общ.)",
    "category_achievements": "Достижения",
    "category_nonresident_in_dorm": "Иногородний (в общ.)",
    "case_death_relative": "Смерть родственника",
    "case_birth_child": "Рождение ребенка",
    "case_death_relative_svo": "Смерть родств. (СВО)",
    "case_disease_trauma": "Заболевание/Травма",
    "case_marriage": "Брак",
    "case_emergency": "ЧС / Беженец",
}


def material_aid_categories_keyboard(selected: set) -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for key, label in MATERIAL_AID_CATEGORIES.items():
        is_selected = key in selected
        text = f"{'✅' if is_selected else '⬜'} {label}"
        row.append(InlineKeyboardButton(text=text, callback_data=f"ma_cat_{key}"))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton(text="Готово", callback_data="ma_done")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def events_keyboard(events: list) -> InlineKeyboardMarkup:
    rows = []
    for event in events:
        rows.append([
            InlineKeyboardButton(
                text=event['title'],
                callback_data=f"event_info_{event['id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_register_keyboard(event_id: int, is_registered: bool) -> InlineKeyboardMarkup:
    if is_registered:
        text = "❌ Отменить запись"
        callback = f"event_unregister_{event_id}"
    else:
        text = "✅ Записаться"
        callback = f"event_register_{event_id}"
        
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback)],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="events_list")]
    ])


def appeal_topics_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="Компенсация проезда")],
        [KeyboardButton(text="Единовременная выплата")],
        [KeyboardButton(text="Общие вопросы")],
        [KeyboardButton(text="Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def subscription_keyboard(subs: list) -> InlineKeyboardMarkup:
    categories = {
        "events": "Мероприятия",
        "payments": "Выплаты",
        "benefits": "Льготы",
        "contests": "Конкурсы",
        "mass": "Массовые"
    }
    rows = []
    for code, name in categories.items():
        is_sub = code in subs
        status = "✅" if is_sub else "❌"
        rows.append([
            InlineKeyboardButton(
                text=f"{status} {name}",
                callback_data=f"sub_toggle_{code}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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

def pay_union_fee_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="💳 Сдать профвзнос",
                callback_data="pay_union_fee",
            )
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)


def appeal_topics_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="Компенсация проезда")],
        [KeyboardButton(text="Единовременная выплата")],
        [KeyboardButton(text="Общие вопросы")],
        [KeyboardButton(text="Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def upload_application_types_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Материальная помощь", callback_data="upload_type_material_aid")
            ],
            [
                InlineKeyboardButton(text="Компенсация проезда", callback_data="upload_type_travel")
            ],
            [
                InlineKeyboardButton(text="Компенсация общежития", callback_data="upload_type_dorm")
            ]
        ]
    )

