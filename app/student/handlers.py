from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery
import html

from os import getenv
from dotenv import load_dotenv

from app.database import db
from app.student.states import ProfileForm, UnionFeeForm, AppealForm, MaterialAidForm, ApplicationUploadForm
from app.student.validators import (
	validate_student_number,
	validate_bauman_login,
	validate_phone
)
from app.student.status_checker import check_student_applications
from app.student.keyboards import (
    confirm_keyboard, 
    main_menu_keyboard, 
    pay_union_fee_keyboard,
    applications_keyboard,
    application_templates_keyboard,
    events_keyboard,
    event_register_keyboard,
    appeal_topics_keyboard,
    material_aid_type_keyboard,
    material_aid_categories_keyboard,
    material_aid_travel_keyboard,
    upload_application_types_keyboard
)
from app.student.schedule import schedule_convert
from app.logger import logger
from app.student.pdf_generator import fill_mp_pdf, MPProfile
from datetime import datetime
from pathlib import Path
from app.middleware import AlbumMiddleware


load_dotenv()
router = Router(name="student")
router.message.middleware(AlbumMiddleware())


@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext) -> None:
	
	telegram_id = message.from_user.id
	username = message.from_user.username

	user = await _get_user_record(telegram_id)
	
	# Обновляем имя пользователя, если оно изменилось или не было установлено
	if user and username:
		await db.execute(
			"UPDATE users SET username = $1 WHERE telegram_id = $2",
			username, telegram_id
		)

	if user:
		await message.answer(
			"Привет! Выбери действие:",
			parse_mode=ParseMode.HTML,
			reply_markup=main_menu_keyboard(),
		)

		if (
			user["first_name"] is None
			or user["last_name"] is None
			or user["group_name"] is None
			or user["student_number"] is None
			or user["bauman_login"] is None
			or user["phone"] is None
		):
			await _request_profile_filling(message)
			await state.set_state(ProfileForm.data)
		else:
			await message.answer(
				"Ты уже зарегистрирован.\n"
				"Посмотреть свои данные можно через кнопку «Профиль».\n"
			)
		return

	# Если пользователя нет - запрашиваем согласие
	await message.answer(
		"👋 Привет! Я бот Профсоюза студентов факультета ИУ.\n\n"
		"Для работы мне понадобятся твои данные: ФИО, группа, номер студенческого и телефон.\n\n"
		"📜 <b>Согласие на обработку персональных данных</b>\n"
		"Нажимая кнопку «Согласен», вы даете согласие на обработку своих персональных данных "
		"в соответствии с Федеральным законом от 27.07.2006 № 152-ФЗ «О персональных данных» "
		"для целей функционирования данного бота и деятельности Профсоюзной организации.",
		parse_mode=ParseMode.HTML,
		reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
			[types.InlineKeyboardButton(text="✅ Согласен", callback_data="consent_agree")]
		])
	)


@router.callback_query(F.data == "consent_agree")
async def consent_agree_handler(callback: CallbackQuery, state: FSMContext) -> None:
	await callback.message.edit_reply_markup(reply_markup=None)
	await callback.message.answer("✅ Согласие принято.")
	
	await _request_profile_filling(callback.message)
	await state.set_state(ProfileForm.data)
	await callback.answer()


@router.message(F.text == "Профиль")
async def profile_handler(message: types.Message) -> None:
	
	telegram_id = message.from_user.id

	try:
		user = await _get_user_record(telegram_id)

		text = (
			"📋 Твой профиль:\n\n"
			f"Фамилия: {user['last_name']}\n"
			f"Имя: {user['first_name']}\n"
			f"Отчество: {user['patronymic'] or '—'}\n"
			f"Группа: {user['group_name'] or 'не указана'}\n"
			f"Студ. билет: {user['student_number'] or 'не указан'}\n"
			f"Бауман логин: {user['bauman_login'] or 'не указан'}\n"
			f"Телефон: {user['phone'] or 'не указан'}\n"
		)

		await message.answer(text)

	except Exception as exc:
		logger.error(f"Ошибка при просмотре профиля: {exc}")
		await message.answer("Произошла ошибка при получении профиля.")


@router.message(ProfileForm.data)
async def collect_profile_data(message: types.Message, state: FSMContext) -> None:

	lines = [line.strip() for line in message.text.splitlines() if line.strip()]

	if len(lines) != 7:
		await message.answer(
			"❌ Неверное количество строк.\n\n"
			"Нужно отправить ОДНО сообщение с 7 строками:\n"
			"1) Фамилия\n"
			"2) Имя\n"
			"3) Отчество или '-'\n"
			"4) Группа (ИУ6-54Б)\n"
			"5) Номер студенческого (например: 23У1101, 23УМ1101, 23УА045)\n"
			"6) Бауманский логин (например: ivan_petrov или s123456)\n"
			"7) Телефон (например: +7 999 123-45-67)\n\n"
		)
		return

	last_raw, first_raw, patronymic_raw, group_raw, stud_raw, login_raw, phone_raw = lines

	last_name = last_raw.title()
	first_name = first_raw.title()
	patronymic = None if patronymic_raw == "-" else patronymic_raw.title()
	group_name = group_raw.upper()
	student_number = stud_raw.upper()
	bauman_login = login_raw.strip()
	phone = phone_raw.strip()

	valid_stud, err_stud = validate_student_number(student_number)
	if not valid_stud:
		await message.answer(
			f"❌ Ошибка в номере студенческого: {err_stud}\n\n"
			"Примеры:\n"
			"23У001\n"
			"23У1101\n"
			"23УМ1101\n"
			"23УА045\n\n"
			"Попробуй ещё раз, отправь 7 строк заново."
		)
		return

	valid_login, err_login = validate_bauman_login(bauman_login)
	if not valid_login:
		await message.answer(
			f"❌ Ошибка в бауманском логине: {err_login}\n\n"
			"Примеры:\n"
			"sna23mk048\n"
			"Попробуй ещё раз, отправь 7 строк заново."
		)
		return

	valid_phone, err_phone = validate_phone(phone)
	if not valid_phone:
		await message.answer(
			f"❌ Ошибка в телефоне: {err_phone}\n\n"
			"Примеры:\n"
			"+7 999 123-45-67\n"
			"8 (999) 123 45 67\n\n"
			"Попробуй ещё раз, отправь 7 строк заново."
		)
		return

	await state.update_data(
		last_name=last_name,
		first_name=first_name,
		patronymic=patronymic,
		group_name=group_name,
		student_number=student_number,
		bauman_login=bauman_login,
		phone=phone,
	)

	await show_profile_for_confirmation(message, state)
	await state.set_state(ProfileForm.confirm)


@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await callback.message.answer(
		"Ок, заполним профиль заново.\n\n"
		"Отправь одно сообщение с 6 строками:\n"
		"1) Фамилия\n"
		"2) Имя\n"
		"3) Отчество или '-'\n"
		"4) Группа (ИУ6-54Б)\n"
		"5) Номер студенческого\n"
		"6) Бауманский логин\n"
		"7) Телефон\n\n"
	)
	await state.set_state(ProfileForm.data)
	await callback.answer()


async def show_profile_for_confirmation(
	message: types.Message,
	state: FSMContext,
) -> None:
	data = await state.get_data()

	text = (
		"📋 Проверь свои данные:\n\n"
		f"Фамилия: {data['last_name']}\n"
		f"Имя: {data['first_name']}\n"
		f"Отчество: {data['patronymic'] or '—'}\n"
		f"Группа: {data['group_name']}\n"
		f"Студенческий: {data['student_number']}\n"
		f"Бауманский логин: {data['bauman_login']}\n"
		f"Телефон: {data['phone']}\n\n"
		"Если всё верно — нажми «✅ Подтвердить данные».\n"
		"Если нужно всё ввести заново — «✏ Перезаполнить данные»."
	)

	await message.answer(
		text,
		reply_markup=confirm_keyboard(allow_edit=True),
	)


@router.message(lambda msg: msg.text == "Расписание")
async def send_schedule(message: types.Message) -> None:
	try:
		pages = await schedule_convert(
			credentials_path="source/creds.json",
			document_id=getenv("SCHEDULE_ID"),
		)

		if not pages:
			raise RuntimeError("Не удалось преобразовать расписание в PNG")

		await message.answer("Ожидайте...")
		for index, image_bytes in enumerate(pages, start=1):
			caption = "📄 Расписание дежурств" if index == 1 else None
			await message.answer_photo(
				photo=types.BufferedInputFile(
					file=image_bytes,
					filename=f"schedule_page_{index}.png",
				),
				caption=caption,
			)

	except Exception as exc:
		logger.error(f"Ошибка отправки расписания: {exc}")
		await message.answer("Ошибка получения расписания.")


@router.message(lambda msg: msg.text == "Карта")
async def send_map(message: types.Message) -> None:
	try:
		photo = types.FSInputFile("source/map.jpg")
		await message.answer_photo(photo, caption="📍 Маршрут до профкома ИУ")
	except Exception as exc:
		logger.error(f"Ошибка отправки карты: {exc}")
		await message.answer("Ошибка при загрузке карты.")


@router.callback_query(F.data == "confirm_profile")
async def confirm_profile(callback: CallbackQuery, state: FSMContext) -> None:
	data = await state.get_data()
	telegram_id = callback.from_user.id

	try:
		user = await _get_user_record(telegram_id)

		if (
			user is not None
			and user["first_name"] is not None
			and user["last_name"] is not None
			and user["group_name"] is not None
			and user["student_number"] is not None
			and user["bauman_login"] is not None
			and user["phone"] is not None
		):
			await callback.message.answer(
				"Твой профиль уже подтверждён ранее.\n"
				"Редактирование через бота недоступно."
			)
			await state.clear()
			await callback.answer()
			return

		role_row = await db.fetchrow(
			"SELECT id FROM roles WHERE code = 'student'"
		)
		role_id = role_row["id"] if role_row is not None else None

		first = data["first_name"].replace("'", "''")
		last = data["last_name"].replace("'", "''")
		patronymic = (
			None if data["patronymic"] is None
			else data["patronymic"].replace("'", "''")
		)
		group = data["group_name"].replace("'", "''")
		student = data["student_number"].replace("'", "''")
		login = data["bauman_login"].replace("'", "''")
		phone = data["phone"].replace("'", "''")
		username = callback.from_user.username
		username_sql = f"'{username}'" if username else "NULL"

		patronymic_sql = "NULL" if patronymic is None else f"'{patronymic}'"
		role_sql = "NULL" if role_id is None else str(int(role_id))

		if user is None:
			query = f"""
				INSERT INTO users (
					telegram_id,
					first_name,
					last_name,
					patronymic,
					group_name,
					student_number,
					bauman_login,
					role_id,
					phone,
					username
				)
				VALUES (
					{int(telegram_id)},
					'{first}',
					'{last}',
					{patronymic_sql},
					'{group}',
					'{student}',
					'{login}',
					{role_sql},
					'{phone}',
					{username_sql}
				)
			"""
			await db.execute(query)
		else:
			query = f"""
				UPDATE users SET
					first_name     = '{first}',
					last_name      = '{last}',
					patronymic     = {patronymic_sql},
					group_name     = '{group}',
					student_number = '{student}',
					bauman_login   = '{login}',
					role_id        = COALESCE(role_id, {role_sql}),
					update_date    = CURRENT_TIMESTAMP,
					phone          = '{phone}',
					username       = {username_sql}
				WHERE telegram_id = {int(telegram_id)}
			"""
			await db.execute(query)

		await callback.message.answer(
			"✅ Данные сохранены.\n"
			"Профиль подтверждён. Теперь редактирование через бота запрещено."
		)
		await state.clear()
		await callback.answer()

	except Exception as exc:
		logger.error(f"Ошибка при сохранении профиля: {exc}")
		await callback.message.answer(
			"Произошла ошибка при сохранении профиля."
		)
		await callback.answer()


async def _request_profile_filling(message: types.Message) -> None:
	await message.answer(
		"Похоже, ты ещё не зарегистрирован в системе.\n\n"
		"Отправь одно сообщение со всеми данными в таком формате (по строчкам):\n\n"
		"Фамилия\n"
		"Имя\n"
		"Отчество или '-' если нет\n"
		"Группа (например: ИУ6-54Б)\n"
		"Номер студенческого (например: 23У1101, 23УМ1101, 23УА045)\n"
		"Бауманский логин (например: ivan_petrov или s123456)\n"
		"Телефон (например: +7 999 123-45-67)\n\n"
		"Просто скопируй шаблон и подставь свои данные."
	)


async def _get_user_record(telegram_id: int):
	return await db.fetchrow(
		f"""
		SELECT
			id,
			first_name,
			last_name,
			patronymic,
			student_number,
			group_name,
			bauman_login,
			role_id,
			phone
		FROM users
		WHERE telegram_id = {int(telegram_id)}
		"""
	)

@router.message(F.text == "Подать заявление")
async def applications_menu(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=applications_keyboard())


@router.message(F.text == "Назад")
async def back_to_main_menu(message: types.Message):
    await message.answer("Главное меню", reply_markup=main_menu_keyboard())


@router.message(F.text == "Скачать бланк")
async def download_template_menu(message: types.Message):
    await message.answer("Выберите тип заявления:", reply_markup=application_templates_keyboard())


@router.message(F.text == "Загрузить заявление")
async def upload_application_menu(message: types.Message):
    await message.answer("Выберите тип заявления:", reply_markup=upload_application_types_keyboard())


@router.callback_query(F.data.startswith("upload_type_"))
async def start_upload_application(callback: CallbackQuery, state: FSMContext):
    upload_type = callback.data.replace("upload_type_", "")
    
    # Сопоставляем тип с читаемым названием или кодом
    type_map = {
        "material_aid": "Материальная помощь",
        "travel": "Компенсация проезда",
        "dorm": "Компенсация общежития"
    }
    
    type_name = type_map.get(upload_type, "Заявление")
    
    await state.update_data(upload_type=upload_type, type_name=type_name)
    
    await callback.message.answer(
        f"Выбрано: {type_name}\n\n"
        "📎 Отправьте фото или файл заявления (PDF/JPG).\n"
        "Можно отправить несколько файлов (альбомом)."
    )
    await state.set_state(ApplicationUploadForm.file)
    await callback.answer()


@router.message(ApplicationUploadForm.file)
async def process_application_upload(message: types.Message, state: FSMContext, album: list[types.Message] = None):
    if not message.document and not message.photo and not album:
        await message.answer("Пожалуйста, отправьте файл или фото.")
        return

    data = await state.get_data()
    type_name = data.get("type_name", "Заявление")
    
    user = await _get_user_record(message.from_user.id)
    if not user:
        await message.answer("Сначала заполните профиль.")
        await state.clear()
        return

    try:
        await db.execute("INSERT INTO application_types (code, name) VALUES ('document', 'Документ') ON CONFLICT (code) DO NOTHING")
        await db.execute("INSERT INTO application_statuses (code, name) VALUES ('pending', 'На рассмотрении') ON CONFLICT (code) DO NOTHING")
    except Exception:
        pass

    type_id = await db.fetchval("SELECT id FROM application_types WHERE code = 'document'")
    status_id = await db.fetchval("SELECT id FROM application_statuses WHERE code = 'pending'")

    file_ids = []
    if album:
        for msg in album:
            if msg.document:
                file_ids.append(msg.document.file_id)
            elif msg.photo:
                file_ids.append(msg.photo[-1].file_id)
    elif message.document:
        file_ids.append(message.document.file_id)
    elif message.photo:
        file_ids.append(message.photo[-1].file_id)
        
    file_id_str = ",".join(file_ids) if file_ids else None
    
    subject = f"Загрузка: {type_name}"
    description = "Загружено через бота"

    await db.execute(
        """
        INSERT INTO applications (user_id, type_id, status_id, subject, description, file_id)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        user['id'], type_id, status_id, subject, description, file_id_str
    )

    await message.answer("✅ Заявление загружено!", reply_markup=main_menu_keyboard())
    await state.clear()


@router.callback_query(F.data == "tpl_material_aid")
async def start_material_aid_flow(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    user = await _get_user_record(telegram_id)

    if not user:
        await callback.answer("Сначала заполните профиль!", show_alert=True)
        return
    
    await callback.message.answer("Выберите вид материальной поддержки:", reply_markup=material_aid_type_keyboard())
    await state.set_state(MaterialAidForm.support_type)
    await callback.answer()


@router.callback_query(MaterialAidForm.support_type, F.data.startswith("ma_type_"))
async def process_ma_type(callback: CallbackQuery, state: FSMContext):
    ma_type = callback.data
    
    if ma_type == "ma_type_travel":
        await callback.message.answer("Уточните тип компенсации проезда:", reply_markup=material_aid_travel_keyboard())
        await state.set_state(MaterialAidForm.travel_type)
        await callback.answer()
        return

    # Сопоставляем данные callback с ключами PDF
    type_map = {
        "ma_type_one_time": "support_one_time",
        "ma_type_dorm": "support_dorm_payment"
    }
    
    selected_type = type_map.get(ma_type)
    await state.update_data(support_type=selected_type)
    
    if selected_type == "support_dorm_payment":
        await callback.message.answer("Введите номер общежития и комнату (например: 10, 505):")
        await state.set_state(MaterialAidForm.dorm_info)
    else:
        await state.update_data(categories=[]) # Инициализируем пустой список
        await callback.message.answer(
            "Выберите льготные категории (можно несколько):", 
            reply_markup=material_aid_categories_keyboard(set())
        )
        await state.set_state(MaterialAidForm.categories)
    
    await callback.answer()


@router.callback_query(MaterialAidForm.travel_type, F.data.startswith("ma_travel_"))
async def process_ma_travel(callback: CallbackQuery, state: FSMContext):
    travel_type = callback.data
    
    travel_map = {
        "ma_travel_home": "support_travel_home",
        "ma_travel_treatment": "support_travel_treatment"
    }
    
    selected_subtype = travel_map.get(travel_type)
    
    # Для проезда выбираем как общий "support_travel", так и конкретный подтип
    # Но мы сохраним их как список или обработаем в finish_ma_generation
    # Пока сохраним подтип в 'support_type', но нужно не забыть добавить 'support_travel' позже
    # На самом деле, давайте сохраним список в 'support_type' или просто специальное значение
    
    # Сохраним подтип. В finish_ma_generation проверим, является ли он одним из подтипов проезда
    # и добавим 'support_travel' тоже.
    
    await state.update_data(support_type=selected_subtype)
    
    await state.update_data(categories=[])
    await callback.message.answer(
        "Выберите льготные категории (можно несколько):", 
        reply_markup=material_aid_categories_keyboard(set())
    )
    await state.set_state(MaterialAidForm.categories)
    await callback.answer()


@router.callback_query(MaterialAidForm.travel_type, F.data == "ma_back_to_type")
async def back_to_ma_type(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Выберите вид материальной поддержки:", reply_markup=material_aid_type_keyboard())
    await state.set_state(MaterialAidForm.support_type)
    await callback.answer()


@router.callback_query(MaterialAidForm.support_type, F.data == "ma_cancel")
async def cancel_ma(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Отменено.")
    await state.clear()
    await callback.answer()


@router.message(MaterialAidForm.dorm_info)
async def process_dorm_info(message: types.Message, state: FSMContext):
    text = message.text
    # Простая валидация или просто сохранение
    await state.update_data(dorm_info=text)
    
    await state.update_data(categories=[])
    await message.answer(
        "Выберите льготные категории (можно несколько):", 
        reply_markup=material_aid_categories_keyboard(set())
    )
    await state.set_state(MaterialAidForm.categories)


@router.callback_query(MaterialAidForm.categories, F.data.startswith("ma_cat_"))
async def toggle_ma_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("ma_cat_", "")
    data = await state.get_data()
    categories = set(data.get("categories", []))
    
    if category in categories:
        categories.remove(category)
    else:
        categories.add(category)
        
    await state.update_data(categories=list(categories))
    
    await callback.message.edit_reply_markup(
        reply_markup=material_aid_categories_keyboard(categories)
    )
    await callback.answer()


@router.callback_query(MaterialAidForm.categories, F.data == "ma_done")
async def finish_ma_generation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    telegram_id = callback.from_user.id
    user = await _get_user_record(telegram_id)
    
    support_type = data.get("support_type")
    categories = data.get("categories", [])
    dorm_info = data.get("dorm_info", "")
    
    # Парсим информацию об общежитии, если она есть
    dorm_num = ""
    dorm_room = ""
    if dorm_info:
        parts = dorm_info.replace(",", " ").split()
        if len(parts) >= 1: dorm_num = parts[0]
        if len(parts) >= 2: dorm_room = parts[1]

    fio = f"{user['last_name']} {user['first_name']}"
    if user['patronymic']:
        fio += f" {user['patronymic']}"

    signature = user['last_name'] or ""
    if user['first_name']:
        signature += f" {user['first_name'][0]}."
    if user['patronymic']:
        signature += f"{user['patronymic'][0]}."

    profile = MPProfile(
        fio=fio,
        group=user['group_name'] or "",
        phone=user['phone'] or "",
        email_local=user['bauman_login'] or "",
        dorm_number=dorm_num,
        dorm_room=dorm_room,
        date=datetime.now().strftime("%d.%m.%Y"),
        signature=signature
    )
    
    # Объединяем тип поддержки и категории
    selected_toggles = list(categories)
    if support_type:
        selected_toggles.append(support_type)
        # Если это подтип проезда, также добавляем общий чекбокс проезда
        if support_type in ["support_travel_home", "support_travel_treatment"]:
            selected_toggles.append("support_travel")

    output_path = Path(f"temp/Заявление_МП_{telegram_id}.pdf")
    
    try:
        fill_mp_pdf(
            input_pdf=Path("source/Заявление_МП.pdf"),
            output_pdf=output_path,
            profile=profile,
            selected=selected_toggles
        )
        
        file = types.FSInputFile(output_path, filename="Заявление_МП.pdf")
        await callback.message.answer_document(file, caption="Ваше заявление сформировано.")
        
        if output_path.exists():
            output_path.unlink()
            
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        await callback.message.answer("Ошибка генерации заявления.")
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("ma_"))
async def handle_expired_ma_session(callback: CallbackQuery):
    """Обработчик для кнопок, если состояние было потеряно (например, после перезапуска бота)"""
    await callback.message.answer("⚠️ Сессия истекла. Пожалуйста, начните заполнение заявления заново.")
    await callback.answer()


@router.message(F.text == "Статус заявления")
async def check_application_status(message: types.Message) -> None:
    telegram_id = message.from_user.id
    
    try:
        # Получаем данные студента
        user = await _get_user_record(telegram_id)
        
        if user is None or user["student_number"] is None:
            await message.answer(
                "⚠️ Сначала заполни профиль с номером студенческого.\n\n"
                "Используй кнопку «Профиль» или команду /start"
            )
            return
        
        student_number = user["student_number"]
        last_name = user["last_name"]
        first_name = user["first_name"]
        
        # Показываем "загрузка..."
        await message.answer("⏳ Проверяю статусы... Подожди немного...")
        
        # Проверяем все статусы (используем кэш если есть)
        statuses = await check_student_applications(
            student_number=student_number,
            last_name=last_name,
            first_name=first_name,
            credentials_path="source/creds.json",
            use_cache=True  # Включаем кэширование
        )
        
        # Формируем красивый ответ
        text = "📊 <b>Твои заявления:</b>\n\n"
        
        # Материальная помощь
        mp = statuses.get('material_help', {})
        if mp.get('found'):
            text += f"🟢 <b>Материальная помощь</b>\n{mp.get('text', 'Неизвестно')}\n\n"
        else:
            text += f"🟢 <b>Материальная помощь</b>\nℹ️ Заявление не подано\n\n"
        
        # Компенсация проезда
        kp = statuses.get('travel_compensation', {})
        if kp.get('found'):
            text += f"🟣 <b>Компенсация проезда</b>\n{kp.get('text', 'Неизвестно')}\n\n"
        else:
            text += f"🟣 <b>Компенсация проезда</b>\nℹ️ Заявление не подано\n\n"
        
        # Компенсация общежития
        obsh = statuses.get('housing_compensation', {})
        if obsh.get('found'):
            text += f"🟢 <b>Компенсация общежития</b>\n{obsh.get('text', 'Неизвестно')}"
        else:
            text += f"🟢 <b>Компенсация общежития</b>\nℹ️ Заявление не подано"
        
        text += "\n\n💡 <i>Данные обновляются каждый час</i>"
        
        await message.answer(
            text,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as exc:
        logger.error(f"Ошибка при проверке статусов: {exc}")
        await message.answer(
            "❌ Ошибка при проверке статусов.\n\n"
            "Попробуй ещё раз через немного 🔄"
        )

@router.message(F.text == "Статус профвзноса")
async def union_fee_status(message: types.Message) -> None:
	user = await db.fetchrow(
		"SELECT id FROM users WHERE telegram_id = $1",
		message.from_user.id,
	)
	if not user:
		await message.answer("❌ Не удалось найти твой профиль. Попробуй /start")
		return

	is_paid = await db.fetchval(
		"""
		SELECT EXISTS(
			SELECT 1
			FROM fee_payments
			WHERE user_id = $1 AND status = 'approved'
		)
		""",
		user["id"],
	)

	if is_paid:
		await message.answer("✅ Профвзнос сдан.")
	else:
		# Проверяем, есть ли заявка на рассмотрении
		is_pending = await db.fetchval(
			"""
			SELECT EXISTS(
				SELECT 1
				FROM fee_payments
				WHERE user_id = $1 AND status = 'pending'
			)
			""",
			user["id"],
		)

		if is_pending:
			await message.answer("⏳ Ваш профвзнос находится на проверке.")
		else:
			await message.answer(
				"❌ Профвзнос не найден.\n\n"
				"Нажмите кнопку ниже, чтобы отправить скрин перевода.",
				reply_markup=pay_union_fee_keyboard()
			)


@router.callback_query(F.data == "pay_union_fee")
async def start_union_fee_payment(callback: CallbackQuery, state: FSMContext) -> None:
    qr = types.FSInputFile("source/union_fee_qr.png")

    await callback.message.answer_photo(
        photo=qr,
        caption=(
            "💳 Оплата профвзноса\n"
			"Внесение профсоюзного взноса можно осущиствить двумя способами:\n"
			"1. Перевод по QR-коду\n"
			"2. Перевод по номеру телефона на контакты ниже:\n"
            "Телефон для перевода:\n +7 977 635-52-28\n"
			"Никита Андреевич С. -- Тинькофф Банк\n\n"
            "После перевода отправьте сюда *скрин/чек* одним сообщением."
        ),
        parse_mode=ParseMode.MARKDOWN
    )
    await state.set_state(UnionFeeForm.awaiting_receipt)
    await callback.answer()

@router.message(UnionFeeForm.awaiting_receipt, F.photo)
async def union_fee_receipt_photo(message: types.Message, state: FSMContext) -> None:
    """Студент отправляет скрин профвзноса — берём данные из БД"""
    
    photo = message.photo[-1]
    file_id = photo.file_id

    try:
        # Достаём пользователя из БД
        user = await db.fetchrow(
            """
            SELECT id, first_name, last_name, patronymic, group_name
            FROM users
            WHERE telegram_id = $1
            """,
            message.from_user.id
        )

        if not user:
            await message.answer("❌ Не удалось найти твой профиль. Попробуй /start")
            await state.clear()
            return

        if not user["first_name"] or not user["last_name"] or not user["group_name"]:
            await message.answer(
                "❌ Профиль заполнен не полностью.\n"
                "Пожалуйста, заполни профиль через /start, затем попробуй снова."
            )
            await state.clear()
            return

        # Сохраняем платёж в БД (amount=0, так как точная сумма неизвестна)
        await db.execute(
            """
            INSERT INTO fee_payments (
                user_id,
                amount,
                paid_at,
                method,
                receipt_file_id,
                status,
                comment
            )
            VALUES ($1, 0, CURRENT_TIMESTAMP, 'transfer', $2, 'pending', NULL)
            """,
            user["id"],
            file_id
        )

    except Exception as exc:
        logger.error(f"Ошибка при сохранении чека профвзноса: {exc}")
        await message.answer("Произошла ошибка при сохранении данных. Попробуйте позже.")
        await state.clear()
        return

    await message.answer(
        "✅ Принято! Скрин отправлен на проверку.\n"
        "Статус обновится после обработки профкомом."
    )
    await state.clear()
@router.message(F.text == "Написать обращение")
async def start_appeal(message: types.Message, state: FSMContext) -> None:
    await message.answer(
        "Выберите тему обращения:",
        reply_markup=appeal_topics_keyboard()
    )
    await state.set_state(AppealForm.topic)


@router.message(AppealForm.topic)
async def process_appeal_topic(message: types.Message, state: FSMContext) -> None:
    if message.text == "Отмена":
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        await state.clear()
        return

    if message.text not in ["Компенсация проезда", "Единовременная выплата", "Общие вопросы"]:
        await message.answer("Пожалуйста, выберите тему из меню.")
        return

    await state.update_data(topic=message.text)
    await message.answer(
        f"Тема: {message.text}\n\n"
        "📝 Опишите вашу проблему или вопрос одним сообщением.\n"
        "Вы также можете прикрепить фото к сообщению.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AppealForm.text)


@router.message(AppealForm.text)
async def process_appeal(message: types.Message, state: FSMContext, album: list[types.Message] = None) -> None:
    # Если пришел альбом, берем текст/капшн из первого сообщения с текстом
    text = message.text or message.caption
    if album:
        for msg in album:
            if msg.caption:
                text = msg.caption
                break
            if msg.text:
                text = msg.text
                break
    
    if not text and not message.photo and not album:
        await message.answer("Пожалуйста, отправьте текстовое сообщение или фото.")
        return
        
    if not text:
        text = "Без описания"

    data = await state.get_data()
    topic = data.get("topic", "Общие вопросы")

    user = await _get_user_record(message.from_user.id)
    if not user:
        await message.answer("Сначала заполните профиль.")
        await state.clear()
        return

    # Убеждаемся, что типы/статусы существуют (ленивая инициализация)
    try:
        await db.execute("INSERT INTO application_types (code, name) VALUES ('appeal', 'Обращение') ON CONFLICT (code) DO NOTHING")
        await db.execute("INSERT INTO application_statuses (code, name) VALUES ('pending', 'На рассмотрении') ON CONFLICT (code) DO NOTHING")
        await db.execute("INSERT INTO application_statuses (code, name) VALUES ('answered', 'Отвечено') ON CONFLICT (code) DO NOTHING")
    except Exception:
        pass

    type_id = await db.fetchval("SELECT id FROM application_types WHERE code = 'appeal'")
    status_id = await db.fetchval("SELECT id FROM application_statuses WHERE code = 'pending'")

    file_ids = []
    if album:
        for msg in album:
            if msg.photo:
                file_ids.append(msg.photo[-1].file_id)
    elif message.photo:
        file_ids.append(message.photo[-1].file_id)
        
    file_id_str = ",".join(file_ids) if file_ids else None

    await db.execute(
        """
        INSERT INTO applications (user_id, type_id, status_id, subject, description, file_id)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        user['id'], type_id, status_id, topic, text, file_id_str
    )

    await message.answer("✅ Ваше обращение отправлено!", reply_markup=main_menu_keyboard())
    await state.clear()


@router.callback_query(F.data.startswith("read_appeal_"))
async def read_appeal_reply(callback: CallbackQuery) -> None:
    appeal_id = int(callback.data.split("_")[-1])
    
    row = await db.fetchrow(
        "SELECT admin_reply FROM applications WHERE id = $1",
        appeal_id
    )
    
    if not row or not row['admin_reply']:
        await callback.answer("Ответ не найден.", show_alert=True)
        return

    text = (
        f"📩 <b>Ответ на обращение #{appeal_id}</b>\n\n"
        f"{html.escape(row['admin_reply'])}"
    )
    
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.message(F.text == "Мероприятия")
async def events_handler(message: types.Message) -> None:
    events = await db.fetch("SELECT id, title FROM events ORDER BY created_at DESC")
    
    if not events:
        await message.answer("На данный момент нет доступных мероприятий.")
        return

    await message.answer(
        "Список ближайших мероприятий:",
        reply_markup=events_keyboard(events)
    )


@router.callback_query(F.data.startswith("event_info_"))
async def event_info_handler(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split("_")[-1])
    
    event = await db.fetchrow("SELECT * FROM events WHERE id = $1", event_id)
    if not event:
        await callback.answer("Мероприятие не найдено.", show_alert=True)
        return

    # Проверяем, зарегистрирован ли пользователь
    user = await _get_user_record(callback.from_user.id)
    is_registered = False
    if user:
        exists = await db.fetchval(
            """
            SELECT 1 FROM applications a
            JOIN application_types t ON a.type_id = t.id
            WHERE a.user_id = $1 AND a.related_event_id = $2 AND t.code = 'event'
            """,
            user['id'], event_id
        )
        is_registered = bool(exists)

    text = (
        f"📅 <b>{event['title']}</b>\n\n"
        f"{event['description'] or 'Описание отсутствует.'}"
    )
    
    await callback.message.answer(
        text, 
        parse_mode="HTML",
        reply_markup=event_register_keyboard(event_id, is_registered)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("event_register_"))
async def event_register_handler(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split("_")[-1])
    user = await _get_user_record(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка пользователя.")
        return

    type_id = await db.fetchval("SELECT id FROM application_types WHERE code = 'event'")
    status_id = await db.fetchval("SELECT id FROM application_statuses WHERE code = 'approved'")

    # Проверяем, уже ли зарегистрирован
    exists = await db.fetchval(
        "SELECT id FROM applications WHERE user_id = $1 AND related_event_id = $2 AND type_id = $3",
        user['id'], event_id, type_id
    )
    
    if exists:
        await callback.answer("Вы уже записаны.", show_alert=True)
        return

    event = await db.fetchrow("SELECT title FROM events WHERE id = $1", event_id)
    
    await db.execute(
        """
        INSERT INTO applications (user_id, type_id, status_id, subject, related_event_id)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user['id'], type_id, status_id, f"Запись на: {event['title']}", event_id
    )
    
    await callback.answer("Вы успешно записались!")
    
    # Обновляем информационное сообщение (чтобы обновить кнопку на 'Отменить запись')
    # Мы не можем легко вызвать event_info_handler, так как он ожидает callback с другими данными
    # Но мы можем просто отправить новое сообщение или отредактировать старое.
    # На самом деле, event_info_handler отправляет НОВОЕ сообщение.
    # В идеале мы должны отредактировать существующее сообщение.
    # Попробуем переиспользовать логику или просто скопировать её.
    
    # Повторная проверка регистрации
    is_registered = True
    
    text = (
        f"📅 <b>{event['title']}</b>\n\n"
        f"Описание отсутствует." # У нас нет описания здесь без повторного запроса
    )
    # Запрашиваем мероприятие снова, чтобы быть уверенными
    event_full = await db.fetchrow("SELECT * FROM events WHERE id = $1", event_id)
    text = (
        f"📅 <b>{event_full['title']}</b>\n\n"
        f"{event_full['description'] or 'Описание отсутствует.'}"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=event_register_keyboard(event_id, is_registered)
    )


@router.callback_query(F.data.startswith("event_unregister_"))
async def event_unregister_handler(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split("_")[-1])
    user = await _get_user_record(callback.from_user.id)
    
    if not user:
        return

    type_id = await db.fetchval("SELECT id FROM application_types WHERE code = 'event'")
    
    await db.execute(
        "DELETE FROM applications WHERE user_id = $1 AND related_event_id = $2 AND type_id = $3",
        user['id'], event_id, type_id
    )
    
    await callback.answer("Вы отменили запись.")
    
    # Обновляем информационное сообщение
    event_full = await db.fetchrow("SELECT * FROM events WHERE id = $1", event_id)
    text = (
        f"📅 <b>{event_full['title']}</b>\n\n"
        f"{event_full['description'] or 'Описание отсутствует.'}"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=event_register_keyboard(event_id, False)
    )


@router.callback_query(F.data == "events_list")
async def events_list_callback(callback: CallbackQuery) -> None:
    events = await db.fetch("SELECT id, title FROM events ORDER BY created_at DESC")
    
    if not events:
        await callback.answer("Нет мероприятий.", show_alert=True)
        return

    await callback.message.edit_text(
        "Список ближайших мероприятий:",
        reply_markup=events_keyboard(events)
    )
