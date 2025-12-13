from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery

from os import getenv
from dotenv import load_dotenv

from app.database import db
from app.student.states import ProfileForm
from app.student.validators import (
	validate_student_number,
	validate_bauman_login,
	validate_phone,
)
from app.student.keyboards import confirm_keyboard, main_menu_keyboard
from app.student.schedule import schedule_convert
from app.logger import logger


load_dotenv()
router = Router(name="student")


@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext) -> None:
	"""Greet user and collect profile info when needed."""
	telegram_id = message.from_user.id

	user = await _get_user_record(telegram_id)

	await message.answer(
		"Привет! Выбери действие:",
		parse_mode=ParseMode.HTML,
		reply_markup=main_menu_keyboard(),
	)

	if user is None:
		await _request_profile_filling(message)
		await state.set_state(ProfileForm.data)
		return

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
		return

	await message.answer(
		"Ты уже зарегистрирован.\n"
		"Посмотреть свои данные можно через кнопку «Профиль».\n"
	)


@router.message(F.text == "Профиль")
async def profile_handler(message: types.Message) -> None:
	"""Send stored profile details."""
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
	"""Validate and store profile data within FSM."""
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
	"""Reset profile wizard before confirmation."""
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
	"""Render collected data preview before DB save."""
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
	"""Send duty schedule converted from Google Docs into PNG images."""
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
	"""Send the route map to the union office."""
	try:
		photo = types.FSInputFile("source/map.jpg")
		await message.answer_photo(photo, caption="📍 Маршрут до профкома ИУ")
	except Exception as exc:
		logger.error(f"Ошибка отправки карты: {exc}")
		await message.answer("Ошибка при загрузке карты.")


@router.callback_query(F.data == "confirm_profile")
async def confirm_profile(callback: CallbackQuery, state: FSMContext) -> None:
	"""Persist verified profile into the database."""
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
					phone
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
					'{phone}'
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
					phone          = '{phone}'
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
	"""Send instructions on how to provide profile data."""
	await message.answer(
		"Похоже, ты ещё не зарегистрирован в системе.\n\n"
		"Отправь одно сообщение со всеми данными в таком формате (по строчкам):\n\n"
		"1) Фамилия\n"
		"2) Имя\n"
		"3) Отчество или '-' если нет\n"
		"4) Группа (например: ИУ6-54Б)\n"
		"5) Номер студенческого (например: 23У1101, 23УМ1101, 23УА045)\n"
		"6) Бауманский логин (например: ivan_petrov или s123456)\n"
		"7) Телефон (например: +7 999 123-45-67)\n\n"
		"Просто скопируй шаблон и подставь свои данные."
	)


async def _get_user_record(telegram_id: int):
	"""Return basic user data or None if the user is not registered."""
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
