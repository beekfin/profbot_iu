from aiogram.fsm.state import State, StatesGroup

class AdminAppealReply(StatesGroup):
    text = State()
    appeal_id = State()


class MailingForm(StatesGroup):
    recipients = State()
    message = State()
    confirm = State()


class AdminApplicationReview(StatesGroup):
    reason = State()
