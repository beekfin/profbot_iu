from aiogram.fsm.state import State, StatesGroup


class ProfileForm(StatesGroup):
    data = State()
    last_name = State()
    first_name = State()
    patronymic = State()
    group = State()
    student_number = State()
    bauman_login = State()
    confirm = State()
    phone = State()

class UnionFeeForm(StatesGroup):
    awaiting_receipt = State()


class AppealForm(StatesGroup):
    topic = State()
    text = State()


class ApplicationUploadForm(StatesGroup):
    type = State()
    file = State()


class MaterialAidForm(StatesGroup):
    support_type = State()
    travel_type = State()
    dorm_info = State()
    categories = State()
