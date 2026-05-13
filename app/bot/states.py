from aiogram.fsm.state import State, StatesGroup


class KYCStates(StatesGroup):
    """مراحل احراز هویت"""
    waiting_full_name = State()
    waiting_national_id = State()
    waiting_phone = State()
    waiting_document = State()
    waiting_confirm = State()


class OrderStates(StatesGroup):
    """مراحل ثبت سفارش"""
    selecting_type = State()
    selecting_currency = State()
    entering_amount = State()
    confirming = State()


class AdminStates(StatesGroup):
    """مراحل ادمین"""
    waiting_reject_reason = State()
    waiting_internal_rate = State()
