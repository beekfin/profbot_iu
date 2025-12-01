"""Compatibility shim for separating student and admin handlers."""

from app.admin import admin_router
from app.student import student_router


router = student_router
__all__ = ["student_router", "admin_router", "router"]


_LEGACY_HANDLERS_SOURCE = """
	valid_login, err_login = validate_bauman_login(bauman_login)
	if not valid_login:
		await message.answer(
			f"❌ Ошибка в бауманском логине: {err_login}\n\n"
			"Примеры:\n"
			"sna23mk048\n"
			"Попробуй ещё раз, отправь 7 строк заново."
		)
		return

	# Валидация телефона
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

	# Сохраняем всё во временное состояние FSM, в БД ещё не пишем
	await state.update_data(
		last_name=last_name,
		first_name=first_name,
		patronymic=patronymic,
		group_name=group_name,
		student_number=student_number,
		bauman_login=bauman_login,
		phone=phone,
	)

	# Показываем сводку + кнопки
	await show_profile_for_confirmation(message, state)
	await state.set_state(ProfileForm.confirm)

# Перезаполнить данные (до подтверждения)

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


# Показ профиля для подтверждения

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


# Подтверждение профиля -> запись в БД

@router.callback_query(F.data == "confirm_profile")
async def confirm_profile(callback: CallbackQuery, state: FSMContext) -> None:
	data = await state.get_data()
	telegram_id = callback.from_user.id

	try:
		# Проверяем, есть ли уже полный профиль
		user = await db.fetchrow(
			f"""
			SELECT
				id,
				first_name,
				last_name,
				group_name,
				student_number,
				bauman_login,
				phone
			FROM users
			WHERE telegram_id = {int(telegram_id)}
			"""
		)

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
			# Есть незавершённая запись -> UPDATE
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

	except Exception as e:
		logger.error(f"Ошибка при сохранении профиля: {e}")
		await callback.message.answer(
			"Произошла ошибка при сохранении профиля."
		)
		await callback.answer()


# Расписание

@router.message(lambda msg: msg.text == "Расписание")
async def send_schedule(message: types.Message):
	try:
		pdf_bytes = await schedule_convert(
			credentials_path="source/creds.json",
			document_id=getenv("SCHEDULE_ID"),
		)

		await message.answer("Ожидайте...")
		await message.answer_document(
			document=types.BufferedInputFile(
				file=pdf_bytes,
				filename="schedule.pdf",
			),
			caption="📄 Расписание дежурств",
		)

	except Exception as e:
		logger.error(f"Ошибка отправки расписания: {e}")
		await message.answer("Ошибка получения расписания.")


# Карта

@router.message(lambda msg: msg.text == "Карта")
async def send_map(message: types.Message):
	try:
		photo = types.FSInputFile("source/map.jpg")
		await message.answer_photo(photo, caption="📍 Маршрут до профкома ИУ")
	except Exception as e:
		logger.error(f"Ошибка отправки карты: {e}")
		await message.answer("Ошибка при загрузке карты.")
"""
