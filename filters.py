from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from config import ADMIN_IDS


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id if event.from_user else None
        return user_id in ADMIN_IDS
