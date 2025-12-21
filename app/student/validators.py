import datetime
import re

ALLOWED_FACULTIES = ["У", "УМ", "УА"]


def validate_student_number(value: str) -> tuple[bool, str]:
    value = value.upper().strip()

    if not re.match(r"^\d{2}[А-ЯA-Z]{1,2}\d{3,4}$", value):
        return False, "Формат: 23У001 или 23УМ1101"

    year = int(value[:2])

    letters = re.findall(r"[А-ЯA-Z]+", value)[0]
    digits = re.findall(r"\d{3,4}$", value)[0]

    current_year = datetime.datetime.now().year % 100

    if year < 10 or year > current_year:
        return False, "Некорректный год поступления"

    if letters not in ALLOWED_FACULTIES:
        return False, "Допустимые обозначения: У, УМ, УА"

    if int(digits) < 1:
        return False, "Номер дела должен быть от 001"

    return True, "OK"


def validate_bauman_login(value: str) -> tuple[bool, str]:
    value = value.strip()

    if not re.match(r"^[a-zA-Z0-9._-]+$", value):
        return False, "Логин может содержать только латиницу, цифры"

    if len(value) < 3 or len(value) > 20:
        return False, "Длина логина от 3 до 20 символов"

    return True, "OK"


def validate_phone(phone: str) -> tuple[bool, str]:
    phone = phone.strip()

    if not phone:
        return False, "Телефон не может быть пустым."

    if not re.fullmatch(r"[0-9\+\-\s\(\)]{6,30}", phone):
        return False, "Телефон должен содержать только цифры, '+', '-', пробелы и скобки."

    digits = re.sub(r"\D", "", phone)

    if len(digits) != 11:
        return False, "Российский номер должен содержать ровно 11 цифр (пример: +7 999 123-45-67)."

    if digits[0] not in ("7", "8"):
        return False, "Российский номер должен начинаться с '+7' или '8'."

    return True, ""


def validate_group_name(value: str) -> tuple[bool, str]:
    value = value.strip().upper()
    # Пример: ИУ6-54Б, МТ11-12, Э9-11
    if not re.match(r"^[А-ЯA-Z]+\d{1,2}-\d{2,3}[А-ЯA-Z]?$", value):
        return False, "Некорректный формат группы (пример: ИУ6-54Б)"
    return True, ""


def validate_fio(value: str) -> tuple[bool, str]:
    parts = value.strip().split()
    if len(parts) < 2:
        return False, "ФИО должно содержать минимум Фамилию и Имя"
    
    for part in parts:
        if not re.match(r"^[А-Яа-яA-Za-zёЁ\-]+$", part):
            return False, "ФИО может содержать только буквы и дефис"
            
    return True, ""
