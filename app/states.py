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