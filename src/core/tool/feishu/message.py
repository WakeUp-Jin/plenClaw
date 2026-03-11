"""Feishu IM message tools for AI Agent."""

from __future__ import annotations

import json
from typing import Any

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
    ListMessageRequest,
)

from core.tool.feishu.client import FeishuClient
from utils import logger


# ── Tool 1: feishu_send_message ──

feishu_send_message_def = {
    "name": "feishu_send_message",
    "description": "向飞书用户或群组发送消息。receive_id_type 通常使用 chat_id。content 必须是 JSON 字符串。",
    "parameters": {
        "type": "object",
        "properties": {
            "receive_id": {"type": "string", "description": "接收者 ID"},
            "receive_id_type": {
                "type": "string",
                "enum": ["open_id", "user_id", "union_id", "email", "chat_id"],
                "description": "接收者 ID 类型",
            },
            "msg_type": {
                "type": "string",
                "enum": ["text", "post", "interactive"],
                "description": "消息类型",
            },
            "content": {
                "type": "string",
                "description": "消息内容 JSON 字符串，例如文本消息: {\"text\":\"hello\"}",
            },
        },
        "required": ["receive_id", "receive_id_type", "msg_type", "content"],
    },
}


async def feishu_send_message_handler(client: FeishuClient, args: dict) -> str:
    receive_id = args["receive_id"]
    receive_id_type = args["receive_id_type"]
    msg_type = args["msg_type"]
    content = args["content"]

    request = (
        CreateMessageRequest.builder()
        .receive_id_type(receive_id_type)
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type(msg_type)
            .content(content)
            .build()
        )
        .build()
    )

    resp = client.client.im.v1.message.create(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_send_message")
    if err:
        return client.to_json(err)

    return client.to_json({"message_id": resp.data.message_id})


# ── Tool 2: feishu_reply_message ──

feishu_reply_message_def = {
    "name": "feishu_reply_message",
    "description": "回复指定的一条飞书消息，产生引用回复效果",
    "parameters": {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "要回复的消息 ID"},
            "msg_type": {
                "type": "string",
                "enum": ["text", "post", "interactive"],
                "description": "消息类型",
            },
            "content": {"type": "string", "description": "回复内容 JSON 字符串"},
        },
        "required": ["message_id", "msg_type", "content"],
    },
}


async def feishu_reply_message_handler(client: FeishuClient, args: dict) -> str:
    message_id = args["message_id"]
    msg_type = args["msg_type"]
    content = args["content"]

    request = (
        ReplyMessageRequest.builder()
        .message_id(message_id)
        .request_body(
            ReplyMessageRequestBody.builder()
            .msg_type(msg_type)
            .content(content)
            .build()
        )
        .build()
    )

    resp = client.client.im.v1.message.reply(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_reply_message")
    if err:
        return client.to_json(err)

    return client.to_json({"message_id": resp.data.message_id})


# ── Tool 3: feishu_get_message_history ──

feishu_get_message_history_def = {
    "name": "feishu_get_message_history",
    "description": "获取指定会话的历史消息列表",
    "parameters": {
        "type": "object",
        "properties": {
            "container_id": {"type": "string", "description": "会话 ID (chat_id)"},
            "start_time": {"type": "string", "description": "起始时间戳（秒）"},
            "end_time": {"type": "string", "description": "结束时间戳（秒）"},
            "page_size": {
                "type": "integer",
                "description": "每页数量，默认 20，最大 50",
                "default": 20,
            },
        },
        "required": ["container_id"],
    },
}


async def feishu_get_message_history_handler(client: FeishuClient, args: dict) -> str:
    container_id = args["container_id"]
    start_time = args.get("start_time")
    end_time = args.get("end_time")
    page_size = args.get("page_size", 20)

    builder = (
        ListMessageRequest.builder()
        .container_id_type("chat_id")
        .container_id(container_id)
        .page_size(min(page_size, 50))
    )
    if start_time is not None:
        builder = builder.start_time(str(start_time))
    if end_time is not None:
        builder = builder.end_time(str(end_time))

    request = builder.build()

    resp = client.client.im.v1.message.list(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_get_message_history")
    if err:
        return client.to_json(err)

    messages = []
    for item in (resp.data.items or []):
        msg = {
            "sender_id": item.sender.id if item.sender else None,
            "msg_type": item.msg_type,
            "content": item.body.content if item.body else None,
            "create_time": item.create_time,
        }
        messages.append(msg)

    return client.to_json({"messages": messages})
