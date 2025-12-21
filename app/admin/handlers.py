from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
import html
from os import getenv
import csv
from io import StringIO

from app.database import db
from app.logger import logger
from app.admin.keyboards import admin_menu_keyboard, fee_check_keyboard, appeal_answer_keyboard, application_review_keyboard
from app.student.keyboards import main_menu_keyboard
from app.admin.states import AdminAppealReply, MailingForm, AdminApplicationReview


router = Router(name="admin")


@router.message(Command("admin"))
@router.message(F.text == "Админ панель")
async def admin_entrypoint(message: types.Message) -> None:
    """Простая точка входа, проверяющая доступ к функциям администратора."""
    telegram_id = message.from_user.id

    try:
        if not await _user_is_admin(telegram_id):
            await message.answer("⛔️ Доступ запрещён. Режим администратора доступен только сотрудникам профкома.")
            return

        await message.answer(
            "🔐 Добро пожаловать в административный режим.\n"
            "Выберите действие в меню:",
            reply_markup=admin_menu_keyboard()
        )
    except Exception as exc:
        logger.error(f"Ошибка входа в админ-панель: {exc}")
        await message.answer("Не удалось открыть админ-панель. Попробуйте позже.")


@router.message(Command("exit"))
async def exit_admin_mode(message: types.Message) -> None:
    await message.answer(
        "Вы вернулись в меню студента.",
        reply_markup=main_menu_keyboard()
    )


async def _user_is_admin(telegram_id: int) -> bool:
    """Возвращает True, если у пользователя есть роль администратора."""
    try:
        # Сначала проверяем супер-админа
        if await _user_is_super_admin(telegram_id):
            return True

        row = await db.fetchrow(
            """
            SELECT 1
            FROM users u
            JOIN roles r ON r.id = u.role_id
            WHERE u.telegram_id = $1 AND r.code = 'admin'
            """,
            int(telegram_id),
        )
        return row is not None
    except Exception as exc:
        logger.error(f"Не удалось проверить права администратора: {exc}")
        return False


async def _user_is_super_admin(telegram_id: int) -> bool:
    super_admin_id = getenv("SUPER_ADMIN_ID")
    return super_admin_id and str(telegram_id) == str(super_admin_id)


@router.message(Command("add_admin"))
async def add_admin_handler(message: types.Message) -> None:
    if not await _user_is_super_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /add_admin <telegram_id или @username>")
        return
    
    target = args[1]
    user = None

    if target.isdigit():
        user = await db.fetchrow("SELECT telegram_id FROM users WHERE telegram_id = $1", int(target))
    else:
        username = target.lstrip('@')
        user = await db.fetchrow("SELECT telegram_id FROM users WHERE username = $1", username)
    
    if not user:
        await message.answer(f"Пользователь {target} не найден в базе данных бота.")
        return
    
    target_id = user['telegram_id']

    try:
        # Убеждаемся, что роль администратора существует
        await db.execute("INSERT INTO roles (code, name) VALUES ('admin', 'Администратор') ON CONFLICT (code) DO NOTHING")
        admin_role_id = await db.fetchval("SELECT id FROM roles WHERE code = 'admin'")

        # Обновляем роль пользователя
        await db.execute(
            "UPDATE users SET role_id = $1 WHERE telegram_id = $2",
            admin_role_id, target_id
        )
        
        await message.answer(f"Пользователь {target} назначен администратором.")
            
    except Exception as e:
        logger.error(f"Error adding admin: {e}")
        await message.answer("Ошибка при назначении администратора.")


@router.message(Command("remove_admin"))
async def remove_admin_handler(message: types.Message) -> None:
    if not await _user_is_super_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /remove_admin <telegram_id или @username>")
        return
    
    target = args[1]
    user = None

    if target.isdigit():
        user = await db.fetchrow("SELECT telegram_id FROM users WHERE telegram_id = $1", int(target))
    else:
        username = target.lstrip('@')
        user = await db.fetchrow("SELECT telegram_id FROM users WHERE username = $1", username)
    
    if not user:
        await message.answer(f"Пользователь {target} не найден в базе данных бота.")
        return
    
    target_id = user['telegram_id']

    try:
        # Устанавливаем роль студента (по умолчанию)
        student_role_id = await db.fetchval("SELECT id FROM roles WHERE code = 'student'")
        
        if not student_role_id:
             await db.execute("INSERT INTO roles (code, name) VALUES ('student', 'Студент') ON CONFLICT (code) DO NOTHING")
             student_role_id = await db.fetchval("SELECT id FROM roles WHERE code = 'student'")

        await db.execute(
            "UPDATE users SET role_id = $1 WHERE telegram_id = $2",
            student_role_id, target_id
        )
        
        await message.answer(f"Пользователь {target} разжалован.")
            
    except Exception as e:
        logger.error(f"Error removing admin: {e}")
        await message.answer("Ошибка при удалении администратора.")



@router.message(F.text == "Отчеты")
async def reports_handler(message: types.Message) -> None:
    if not await _user_is_admin(message.from_user.id):
        return
    
    # Генерируем CSV для обращений
    appeals = await db.fetch("""
        SELECT a.id, u.last_name, u.first_name, u.group_name, a.subject, a.created_at, s.name as status
        FROM applications a
        JOIN users u ON a.user_id = u.id
        JOIN application_statuses s ON a.status_id = s.id
        WHERE a.type_id = (SELECT id FROM application_types WHERE code = 'appeal')
        ORDER BY a.created_at DESC
    """)
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Фамилия', 'Имя', 'Группа', 'Тема', 'Дата', 'Статус'])
    
    for row in appeals:
        writer.writerow([
            row['id'], row['last_name'], row['first_name'], row['group_name'], 
            row['subject'], row['created_at'].strftime('%Y-%m-%d %H:%M'), row['status']
        ])
        
    output.seek(0)
    file = types.BufferedInputFile(output.getvalue().encode(), filename="appeals_report.csv")
    await message.answer_document(file, caption="📊 Отчет по обращениям")

    # Генерируем CSV для мероприятий
    events_apps = await db.fetch("""
        SELECT a.id, u.last_name, u.first_name, u.group_name, e.title as event_title, a.created_at
        FROM applications a
        JOIN users u ON a.user_id = u.id
        JOIN events e ON a.related_event_id = e.id
        WHERE a.type_id = (SELECT id FROM application_types WHERE code = 'event')
        ORDER BY a.created_at DESC
    """)

    if events_apps:
        output_events = StringIO()
        writer_events = csv.writer(output_events)
        writer_events.writerow(['ID', 'Фамилия', 'Имя', 'Группа', 'Мероприятие', 'Дата записи'])
        
        for row in events_apps:
            writer_events.writerow([
                row['id'], row['last_name'], row['first_name'], row['group_name'], 
                row['event_title'], row['created_at'].strftime('%Y-%m-%d %H:%M')
            ])
            
        output_events.seek(0)
        file_events = types.BufferedInputFile(output_events.getvalue().encode(), filename="events_report.csv")
        await message.answer_document(file_events, caption="🎉 Отчет по записям на мероприятия")


@router.message(F.text == "Проверить взносы")
async def check_fees_handler(message: types.Message) -> None:
    telegram_id = message.from_user.id
    if not await _user_is_admin(telegram_id):
        return
    
    # Добавляем колонку статуса, если её нет    
    try:
        pass
    except Exception:
        pass 

    await _send_next_fee(message)


async def _send_next_fee(message: types.Message) -> None:
    """Отправить следующий профвзнос на проверку (фото + ФИО/группа из БД)"""
    
    # Получаем самый старый pending платёж с данными студента
    row = await db.fetchrow(
        """
        SELECT 
            fp.id,
            fp.receipt_file_id,
            fp.recorded_at,
            u.first_name,
            u.last_name,
            u.patronymic,
            u.group_name
        FROM fee_payments fp
        JOIN users u ON fp.user_id = u.id
        WHERE fp.status = 'pending'
        ORDER BY fp.recorded_at ASC
        LIMIT 1
        """
    )

    if not row:
        await message.answer("✅ Все взносы проверены! Новых заявок нет.")
        return

    # Формируем ФИО (с отчеством если есть)
    fio = f"{html.escape(row['last_name'])} {html.escape(row['first_name'])}"
    if row["patronymic"]:
        fio += f" {html.escape(row['patronymic'])}"

    # Формируем подпись для фото
    caption = (
        f"💰 <b>Проверка профвзноса #{row['id']}</b>\n\n"
        f"👤 <b>Студент:</b> {fio}\n"
        f"🎓 <b>Группа:</b> {html.escape(row['group_name'])}\n"
        f"📅 <b>Дата поступления:</b> {row['recorded_at'].strftime('%d.%m.%Y %H:%M')}"
    )

    try:
        # Отправляем фото со скрина профвзноса
        await message.answer_photo(
            photo=row["receipt_file_id"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=fee_check_keyboard(row["id"])
        )
    except Exception as exc:
        logger.error(f"Ошибка отправки фото профвзноса: {exc}")
        await message.answer(
            f"❌ Не удалось отобразить фото для заявки #{row['id']}.\n\n{caption}",
            parse_mode="HTML",
            reply_markup=fee_check_keyboard(row["id"])
        )


@router.callback_query(F.data.startswith("fee_approve_"))
async def approve_fee(callback: CallbackQuery) -> None:
    payment_id = int(callback.data.split("_")[-1])
    
    # Получаем информацию о пользователе для уведомления
    row = await db.fetchrow(
        """
        SELECT u.telegram_id 
        FROM fee_payments fp
        JOIN users u ON fp.user_id = u.id
        WHERE fp.id = $1
        """,
        payment_id
    )

    await db.execute(
        "UPDATE fee_payments SET status = 'approved' WHERE id = $1",
        payment_id
    )
    
    # Уведомляем пользователя
    if row:
        try:
            await callback.bot.send_message(
                row['telegram_id'],
                f"✅ <b>Ваш профвзнос #{payment_id} одобрен!</b>\nСпасибо за своевременную оплату.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify user about fee approval: {e}")

    await callback.answer("✅ Взнос подтвержден")
    try:
        await callback.message.delete()
    except:
        pass
    
    await _send_next_fee(callback.message)


@router.callback_query(F.data.startswith("fee_reject_"))
async def reject_fee(callback: CallbackQuery) -> None:
    payment_id = int(callback.data.split("_")[-1])
    
    # Получаем информацию о пользователе для уведомления
    row = await db.fetchrow(
        """
        SELECT u.telegram_id 
        FROM fee_payments fp
        JOIN users u ON fp.user_id = u.id
        WHERE fp.id = $1
        """,
        payment_id
    )

    await db.execute(
        "UPDATE fee_payments SET status = 'rejected' WHERE id = $1",
        payment_id
    )
    
    # Уведомляем пользователя
    if row:
        try:
            await callback.bot.send_message(
                row['telegram_id'],
                f"❌ <b>Ваш профвзнос #{payment_id} отклонен.</b>\nПожалуйста, проверьте данные и попробуйте снова.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify user about fee rejection: {e}")

    await callback.answer("❌ Взнос отклонен")
    try:
        await callback.message.delete()
    except:
        pass
    
    await _send_next_fee(callback.message)

@router.message(F.text == "Обращения")
async def list_appeals(message: types.Message) -> None:
    if not await _user_is_admin(message.from_user.id):
        return
    
    await _send_next_appeal(message)

async def _send_next_appeal(message: types.Message) -> None:
    # Убеждаемся, что колонка file_id существует
    try:
        pass
    except Exception:
        pass

    row = await db.fetchrow("""
        SELECT a.id, a.description, a.created_at, u.first_name, u.last_name, u.group_name, a.file_id
        FROM applications a
        JOIN users u ON a.user_id = u.id
        JOIN application_types t ON a.type_id = t.id
        JOIN application_statuses s ON a.status_id = s.id
        WHERE t.code = 'appeal' AND s.code = 'pending'
        ORDER BY a.created_at ASC
        LIMIT 1
    """)

    if not row:
        await message.answer("✅ Все обращения обработаны!")
        return

    text = (
        f"📩 <b>Обращение #{row['id']}</b>\n"
        f"👤 {html.escape(row['last_name'])} {html.escape(row['first_name'])} ({html.escape(row['group_name'])})\n"
        f"📅 {row['created_at'].strftime('%d.%m %H:%M')}\n\n"
        f"{html.escape(row['description'])}"
    )
    
    if row['file_id']:
        file_ids = row['file_id'].split(",")
        try:
            if len(file_ids) > 1:
                media = [types.InputMediaPhoto(media=fid) for fid in file_ids]
                # Подпись только к первому элементу
                media[0].caption = text
                media[0].parse_mode = "HTML"
                await message.answer_media_group(media)
                # Клавиатура отдельно
                await message.answer("Выберите действие:", reply_markup=appeal_answer_keyboard(row['id']))
            else:
                await message.answer_photo(
                    photo=file_ids[0],
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=appeal_answer_keyboard(row['id'])
                )
        except Exception as e:
            logger.error(f"Failed to send appeal photo: {e}")
            await message.answer(
                f"{text}\n\n⚠️ [Ошибка загрузки фото]", 
                parse_mode="HTML", 
                reply_markup=appeal_answer_keyboard(row['id'])
            )
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=appeal_answer_keyboard(row['id']))

@router.callback_query(F.data.startswith("appeal_reply_"))
async def reply_to_appeal(callback: CallbackQuery, state: FSMContext) -> None:
    appeal_id = int(callback.data.split("_")[-1])
    await state.update_data(appeal_id=appeal_id)
    await callback.message.answer("✍️ Введите текст ответа:")
    await state.set_state(AdminAppealReply.text)
    await callback.answer()

@router.message(AdminAppealReply.text)
async def send_appeal_reply(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    appeal_id = data['appeal_id']
    reply_text = message.text

    # Получаем user_id для уведомления
    appeal = await db.fetchrow("SELECT user_id FROM applications WHERE id = $1", appeal_id)
    if not appeal:
        await message.answer("Ошибка: обращение не найдено.")
        await state.clear()
        return

    user = await db.fetchrow("SELECT telegram_id FROM users WHERE id = $1", appeal['user_id'])
    
    # Убеждаемся, что колонка существует
    try:
        pass
    except Exception:
        pass

    # Обновляем статус и сохраняем ответ
    status_id = await db.fetchval("SELECT id FROM application_statuses WHERE code = 'answered'")
    await db.execute(
        "UPDATE applications SET status_id = $1, admin_reply = $2 WHERE id = $3",
        status_id, reply_text, appeal_id
    )

    # Уведомляем пользователя
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📖 Прочитать", callback_data=f"read_appeal_{appeal_id}")]
    ])

    try:
        await message.bot.send_message(
            user['telegram_id'],
            f"🔔 <b>Получен ответ на ваше обращение #{appeal_id}</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await message.answer("✅ Ответ отправлен.")
    except Exception as e:
        await message.answer(f"⚠️ Ответ сохранен, но не удалось отправить уведомление: {e}")

    await state.clear()
    await _send_next_appeal(message)


@router.message(F.text == "Заявления")
async def check_applications_handler(message: types.Message) -> None:
    if not await _user_is_admin(message.from_user.id):
        return
    await _send_next_application(message)


async def _send_next_application(message: types.Message) -> None:
    # Получаем ожидающее заявление
    row = await db.fetchrow(
        """
        SELECT 
            a.id,
            a.subject,
            a.description,
            a.file_id,
            a.created_at,
            u.first_name,
            u.last_name,
            u.group_name,
            u.student_number
        FROM applications a
        JOIN users u ON a.user_id = u.id
        JOIN application_types t ON a.type_id = t.id
        JOIN application_statuses s ON a.status_id = s.id
        WHERE t.code = 'document' AND s.code = 'pending'
        ORDER BY a.created_at ASC
        LIMIT 1
        """
    )

    if not row:
        await message.answer("✅ Все заявления проверены!")
        return

    text = (
        f"📄 <b>Заявление #{row['id']}</b>\n"
        f"👤 {row['last_name']} {row['first_name']} ({row['group_name']})\n"
        f"🆔 {row['student_number']}\n"
        f"📅 {row['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
        f"📌 {row['subject']}\n"
    )

    keyboard = application_review_keyboard(row['id'])

    if row['file_id']:
        file_ids = row['file_id'].split(',')
        if len(file_ids) == 1:
            # Пытаемся определить тип или просто отправляем как документ
            try:
                await message.answer_document(file_ids[0], caption=text, reply_markup=keyboard, parse_mode="HTML")
            except:
                await message.answer_photo(file_ids[0], caption=text, reply_markup=keyboard, parse_mode="HTML")
        else:
            # Медиа-группа
            media = []
            for i, fid in enumerate(file_ids):
                if i == 0:
                    media.append(types.InputMediaDocument(media=fid, caption=text, parse_mode="HTML"))
                else:
                    media.append(types.InputMediaDocument(media=fid))
            
            try:
                await message.answer_media_group(media)
                await message.answer("Выберите действие:", reply_markup=keyboard)
            except:
                # Резервный вариант при ошибке или смешанном контенте
                await message.answer(text, parse_mode="HTML")
                for fid in file_ids:
                    await message.answer_document(fid)
                await message.answer("Выберите действие:", reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("app_approve_"))
async def approve_application(callback: CallbackQuery):
    app_id = int(callback.data.split("_")[-1])
    
    # Обновляем статус
    status_id = await db.fetchval("SELECT id FROM application_statuses WHERE code = 'approved'")
    if not status_id:
         await db.execute("INSERT INTO application_statuses (code, name) VALUES ('approved', 'Одобрено') ON CONFLICT (code) DO NOTHING")
         status_id = await db.fetchval("SELECT id FROM application_statuses WHERE code = 'approved'")

    await db.execute(
        "UPDATE applications SET status_id = $1, admin_reply = 'Заявление принято.' WHERE id = $2",
        status_id, app_id
    )
    
    # Уведомляем пользователя
    row = await db.fetchrow("SELECT user_id, subject FROM applications WHERE id = $1", app_id)
    if row:
        user = await db.fetchrow("SELECT telegram_id FROM users WHERE id = $1", row['user_id'])
        if user:
            try:
                await callback.bot.send_message(
                    user['telegram_id'],
                    f"✅ <b>Ваше заявление одобрено!</b>\n\n{row['subject']}",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    await callback.answer("Заявление одобрено.")
    await callback.message.delete()
    await _send_next_application(callback.message)


@router.callback_query(F.data.startswith("app_reject_"))
async def reject_application_start(callback: CallbackQuery, state: FSMContext):
    app_id = int(callback.data.split("_")[-1])
    await state.update_data(app_id=app_id)
    
    await callback.message.answer(
        "Напишите причину отказа (что не так с заявлением):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AdminApplicationReview.reason)
    await callback.answer()


@router.message(AdminApplicationReview.reason)
async def reject_application_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    app_id = data.get("app_id")
    reason = message.text
    
    status_id = await db.fetchval("SELECT id FROM application_statuses WHERE code = 'rejected'")
    if not status_id:
         await db.execute("INSERT INTO application_statuses (code, name) VALUES ('rejected', 'Отклонено') ON CONFLICT (code) DO NOTHING")
         status_id = await db.fetchval("SELECT id FROM application_statuses WHERE code = 'rejected'")

    await db.execute(
        "UPDATE applications SET status_id = $1, admin_reply = $2 WHERE id = $3",
        status_id, reason, app_id
    )
    
    # Уведомляем пользователя
    row = await db.fetchrow("SELECT user_id, subject FROM applications WHERE id = $1", app_id)
    if row:
        user = await db.fetchrow("SELECT telegram_id FROM users WHERE id = $1", row['user_id'])
        if user:
            try:
                await message.bot.send_message(
                    user['telegram_id'],
                    f"❌ <b>Ваше заявление отклонено.</b>\n\n"
                    f"📌 {row['subject']}\n"
                    f"💬 Причина: {reason}",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    await message.answer("Заявление отклонено.", reply_markup=admin_menu_keyboard())
    await state.clear()
    await _send_next_application(message)


@router.message(F.text == "Индивидуальная рассылка")
async def start_mailing(message: types.Message, state: FSMContext):
    if not await _user_is_admin(message.from_user.id):
        return

    await message.answer(
        "📢 <b>Индивидуальная рассылка</b>\n\n"
        "Отправьте список получателей. Поддерживаются:\n"
        "• Telegram ID (число)\n"
        "• Тег (@username)\n"
        "• Бауманский логин (ivanov_ii)\n"
        "• Номер студенческого (23У123)\n"
        "• Номер телефона (+7999...)\n\n"
        "Каждый получатель с новой строки или через пробел.",
        parse_mode="HTML",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(MailingForm.recipients)


@router.message(MailingForm.recipients)
async def process_recipients(message: types.Message, state: FSMContext):
    raw_text = message.text
    if not raw_text:
        await message.answer("Пожалуйста, отправьте текстовый список.")
        return

    import re
    tokens = re.split(r'[\s,]+', raw_text)
    tokens = [t.strip() for t in tokens if t.strip()]

    if not tokens:
        await message.answer("Список пуст. Попробуйте снова.")
        return

    found_users = []
    not_found = []

    for token in tokens:
        user = None
        # Пробуем по ID
        if token.isdigit():
            user = await db.fetchrow("SELECT telegram_id, first_name, last_name FROM users WHERE telegram_id = $1", int(token))
        
        # Пробуем по Username
        if not user:
            clean_token = token.lstrip('@')
            user = await db.fetchrow("SELECT telegram_id, first_name, last_name FROM users WHERE username = $1", clean_token)

        # Пробуем по Бауманскому логину
        if not user:
            user = await db.fetchrow("SELECT telegram_id, first_name, last_name FROM users WHERE bauman_login = $1", token)
            
        # Пробуем по номеру студенческого
        if not user:
            user = await db.fetchrow("SELECT telegram_id, first_name, last_name FROM users WHERE student_number = $1", token.upper())

        # Пробуем по телефону
        if not user:
            # Удаляем нецифровые символы
            clean_phone = "".join(filter(str.isdigit, token))
            if len(clean_phone) >= 10:
                # Сравниваем последние 10 цифр для обработки +7 и 8
                user = await db.fetchrow(
                    "SELECT telegram_id, first_name, last_name FROM users WHERE RIGHT(regexp_replace(phone, '\D', '', 'g'), 10) = RIGHT($1, 10)",
                    clean_phone
                )

        if user:
            found_users.append(user)
        else:
            not_found.append(token)

    if not found_users:
        await message.answer("❌ Ни одного пользователя не найдено. Проверьте данные и попробуйте снова.")
        return

    await state.update_data(recipients=[u['telegram_id'] for u in found_users])
    
    msg = f"✅ Найдено пользователей: {len(found_users)}\n"
    if not_found:
        msg += f"⚠️ Не найдено: {', '.join(not_found)}\n"
    
    msg += "\nТеперь отправьте сообщение (текст, фото), которое нужно разослать."
    
    await message.answer(msg)
    await state.set_state(MailingForm.message)


@router.message(MailingForm.message)
async def process_mailing_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    recipients = data.get("recipients", [])
    
    if not recipients:
        await message.answer("Список получателей пуст. Начните заново.")
        await state.clear()
        return

    # Отправляем всем
    success_count = 0
    fail_count = 0
    
    await message.answer("⏳ Начинаю рассылку...")
    
    for chat_id in recipients:
        try:
            await message.send_copy(chat_id=chat_id)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            fail_count += 1
            
    await message.answer(
        f"📢 Рассылка завершена.\n"
        f"✅ Успешно: {success_count}\n"
        f"❌ Ошибок: {fail_count}",
        reply_markup=admin_menu_keyboard()
    )
    await state.clear()
