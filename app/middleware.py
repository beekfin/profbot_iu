from typing import Any, Awaitable, Callable, Dict, List
from aiogram import BaseMiddleware
from aiogram.types import Message
import asyncio

class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.5):
        self.latency = latency
        self.album_data: Dict[str, List[Message]] = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if not event.media_group_id:
            return await handler(event, data)

        media_group_id = event.media_group_id

        if media_group_id not in self.album_data:
            self.album_data[media_group_id] = []
            self.album_data[media_group_id].append(event)
            await asyncio.sleep(self.latency)
            
            # После задержки вызываем обработчик с собранными сообщениями
            # Сортируем сообщения по message_id для обеспечения правильного порядка
            self.album_data[media_group_id].sort(key=lambda m: m.message_id)
            data["album"] = self.album_data[media_group_id]
            try:
                return await handler(event, data)
            finally:
                if media_group_id in self.album_data:
                    del self.album_data[media_group_id]
        else:
            self.album_data[media_group_id].append(event)
            return
