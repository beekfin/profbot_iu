from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import html
from app.database import db
from app.logger import logger

router = Router(name="news")

@router.message(F.text == "Новости")
async def news_list_handler(message: types.Message) -> None:
    news_items = await db.fetch("SELECT id, title FROM news ORDER BY created_at DESC LIMIT 5")
    
    buttons = []
    if news_items:
        for item in news_items:
            # Обрезаем заголовок, если он слишком длинный
            title = item['title']
            if len(title) > 30:
                title = title[:27] + "..."
            buttons.append([InlineKeyboardButton(text=title, callback_data=f"view_news_{item['id']}")])
    else:
        buttons.append([InlineKeyboardButton(text="Нет свежих новостей", callback_data="ignore")])
    
    buttons.append([InlineKeyboardButton(text="⚙️ Настроить подписки", callback_data="news_settings")])
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Новости и подписки:", reply_markup=keyboard)


@router.callback_query(F.data == "ignore")
async def ignore_handler(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "news_settings")
async def news_settings_handler(callback: CallbackQuery) -> None:
    user = await db.fetchrow("SELECT id FROM users WHERE telegram_id = $1", callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    user_id = user['id']
    
    # Получаем все категории
    categories = await db.fetch("SELECT id, code, name FROM mailing_categories ORDER BY id")
    
    # Получаем подписки пользователя
    subs = await db.fetch(
        "SELECT category_id FROM mailing_subscriptions WHERE user_id = $1 AND is_active = TRUE", 
        user_id
    )
    user_sub_ids = {row['category_id'] for row in subs}
    
    buttons = []
    for cat in categories:
        is_sub = cat['id'] in user_sub_ids
        status = "✅" if is_sub else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {cat['name']}", 
                callback_data=f"sub_toggle_{cat['id']}"
            )
        ])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="news_back")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Редактируем сообщение или отправляем новое, если это свежая команда (хотя это callback)
    await callback.message.edit_text("Выберите категории новостей, которые хотите получать:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("sub_toggle_"))
async def sub_toggle_handler(callback: CallbackQuery) -> None:
    try:
        cat_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Ошибка данных")
        return

    user = await db.fetchrow("SELECT id FROM users WHERE telegram_id = $1", callback.from_user.id)
    if not user:
        return
    user_id = user['id']
    
    # Обновляем подписку (переключатель)
    # Проверяем текущее состояние
    current_state = await db.fetchval(
        "SELECT is_active FROM mailing_subscriptions WHERE user_id = $1 AND category_id = $2",
        user_id, cat_id
    )
    
    new_state = True
    if current_state is not None:
        new_state = not current_state
        await db.execute(
            "UPDATE mailing_subscriptions SET is_active = $1 WHERE user_id = $2 AND category_id = $3",
            new_state, user_id, cat_id
        )
    else:
        await db.execute(
            "INSERT INTO mailing_subscriptions (user_id, category_id, is_active) VALUES ($1, $2, TRUE)",
            user_id, cat_id
        )
        
    action = "подписались на" if new_state else "отписались от"
    cat_name = await db.fetchval("SELECT name FROM mailing_categories WHERE id = $1", cat_id)
    
    try:
        await callback.answer(f"Вы {action} категорию {cat_name}")
    except Exception:
        pass
    
    # Обновляем клавиатуру
    await news_settings_handler(callback)


@router.callback_query(F.data == "news_back")
async def news_back_handler(callback: CallbackQuery) -> None:
    # Вызываем логику обработчика списка, но редактируем сообщение вместо отправки нового
    news_items = await db.fetch("SELECT id, title FROM news ORDER BY created_at DESC LIMIT 5")
    
    buttons = []
    if news_items:
        for item in news_items:
            title = item['title']
            if len(title) > 30:
                title = title[:27] + "..."
            buttons.append([InlineKeyboardButton(text=title, callback_data=f"view_news_{item['id']}")])
    else:
        buttons.append([InlineKeyboardButton(text="Нет свежих новостей", callback_data="ignore")])
    
    buttons.append([InlineKeyboardButton(text="⚙️ Настроить подписки", callback_data="news_settings")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Новости и подписки:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("view_news_"))
async def view_news_handler(callback: CallbackQuery) -> None:
    news_id = int(callback.data.split("_")[-1])
    
    row = await db.fetchrow("SELECT title, content, image_id, created_at FROM news WHERE id = $1", news_id)
    
    if not row:
        await callback.answer("Новость не найдена.", show_alert=True)
        return
        
    text = f"<b>{html.escape(row['title'])}</b>\n\n{html.escape(row['content'] or '')}\n\n<i>{row['created_at'].strftime('%d.%m.%Y %H:%M')}</i>"
    
    if row['image_id']:
        await callback.message.answer_photo(row['image_id'], caption=text, parse_mode="HTML")
    else:
        await callback.message.answer(text, parse_mode="HTML")
        
    await callback.answer()


@router.channel_post()
async def channel_post_handler(message: types.Message) -> None:
    text = message.text or message.caption or ""
    logger.info(f"Processing channel post: {text[:50]}...")
    if not text:
        return

    # Парсим заголовок и контент
    lines = text.split('\n', 1)
    title = lines[0]
    content = lines[1] if len(lines) > 1 else ""
    
    # Получаем изображение, если оно есть
    image_id = None
    if message.photo:
        image_id = message.photo[-1].file_id
        
    # Сохраняем в БД
    try:
        await db.execute(
            "INSERT INTO news (title, content, image_id) VALUES ($1, $2, $3)",
            title, content, image_id
        )
    except Exception as e:
        logger.error(f"Failed to save news: {e}")

    # Логика подписки
    text_lower = text.lower()
    
    # Сопоставляем хэштеги с кодами БД
    hashtag_map = {
        "#мероприятия": "events",
        "#выплаты": "payments",
        "#льготы": "benefits",
        "#конкурсы": "contests",
        "#массовые": "mass"
    }
    
    matched_codes = []
    for tag, code in hashtag_map.items():
        if tag in text_lower:
            matched_codes.append(code)
            
    logger.info(f"Matched tags: {matched_codes}")

    # Если это мероприятие, сохраняем также в таблицу events
    if "events" in matched_codes:
        try:
            await db.execute(
                "INSERT INTO events (title, description) VALUES ($1, $2)",
                title, content
            )
            logger.info(f"Created event '{title}' from news post")
        except Exception as e:
            logger.error(f"Failed to create event from news: {e}")

    if not matched_codes:
        return
        
    # Находим пользователей, подписанных на ЛЮБУЮ из совпавших категорий
    # Присоединяем mailing_categories для сопоставления кода
    query = """
        SELECT DISTINCT u.telegram_id 
        FROM mailing_subscriptions s
        JOIN users u ON s.user_id = u.id
        JOIN mailing_categories c ON s.category_id = c.id
        WHERE s.is_active = TRUE AND c.code = ANY($1::text[])
    """
    
    try:
        users = await db.fetch(query, matched_codes)
        logger.info(f"Broadcasting to {len(users)} users")
        
        for user in users:
            try:
                await message.copy_to(chat_id=user['telegram_id'])
            except Exception as e:
                logger.error(f"Failed to forward news to {user['telegram_id']}: {e}")
    except Exception as e:
        logger.error(f"Error processing channel post: {e}")
