from __future__ import annotations

import json
import asyncio
from typing import Any, Callable, Awaitable

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)

from channels.feishu.event_handler import parse_message_event
from utils import logger


class FeishuChannel:
    name = "feishu"

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        on_message: Callable[[str, str, str], Awaitable[str]] | None = None,
    ):
        self._app_id = app_id
        self._app_secret = app_secret
        self._on_message = on_message
        self._client = (
            lark.Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .log_level(lark.LogLevel.WARNING)
            .build()
        )
        self._ws_client: lark.ws.Client | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None

    def set_on_message(self, handler: Callable[[str, str, str], Awaitable[str]]) -> None:
        self._on_message = handler

    async def connect(self) -> None:
        self._event_loop = asyncio.get_running_loop()

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_event)
            .build()
        )

        self._ws_client = lark.ws.Client(
            self._app_id,
            self._app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.WARNING,
        )
        self._ws_client.start()
        logger.info("Feishu WebSocket connected (p2p single-chat mode)")

    def _handle_event(self, data: Any) -> None:
        """Sync callback from lark-oapi, bridge to async."""
        parsed = parse_message_event(data)
        if parsed is None:
            return

        if self._on_message and self._event_loop:
            future = asyncio.run_coroutine_threadsafe(
                self._process_message(parsed), self._event_loop
            )
            future.add_done_callback(self._on_future_done)

    async def _process_message(self, parsed: dict[str, Any]) -> None:
        if not self._on_message:
            return

        text = parsed["text"]
        chat_id = parsed["chat_id"]
        open_id = parsed["open_id"]

        try:
            reply = await self._on_message(text, chat_id, open_id)
            if reply:
                await self.send_message(chat_id, reply)
        except Exception as e:
            logger.error("Error processing message: %s", e, exc_info=True)
            try:
                await self.send_message(chat_id, f"处理消息时出错: {e}")
            except Exception:
                logger.error("Failed to send error reply", exc_info=True)

    @staticmethod
    def _on_future_done(future: asyncio.Future) -> None:
        exc = future.exception()
        if exc:
            logger.error("Message processing error: %s", exc, exc_info=True)

    async def send_message(
        self, chat_id: str, content: str, msg_type: str = "text"
    ) -> None:
        if msg_type == "text":
            content_json = json.dumps({"text": content}, ensure_ascii=False)
        else:
            content_json = content

        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type(msg_type)
                .content(content_json)
                .build()
            )
            .build()
        )

        resp = self._client.im.v1.message.create(request)
        if not resp.success():
            logger.error(
                "Failed to send message: code=%s, msg=%s", resp.code, resp.msg
            )

    async def disconnect(self) -> None:
        if self._ws_client:
            logger.info("Feishu WebSocket disconnecting...")
            self._ws_client = None

    def is_connected(self) -> bool:
        return self._ws_client is not None
