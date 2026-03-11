"""飞书任务工具：创建任务、查询任务、更新任务、创建任务列表。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import lark_oapi as lark
from lark_oapi.api.task.v2 import *

from core.tool.feishu.client import FeishuClient
from utils import logger

# ── 工具定义 ──

feishu_create_task_def = {
    "name": "feishu_create_task",
    "description": "创建一个飞书任务",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "任务标题"},
            "description": {"type": "string", "description": "任务详细描述"},
            "due": {"type": "string", "description": "截止时间 ISO 8601 格式"},
            "members": {"type": "array", "items": {"type": "string"}, "description": "执行者 user_id 列表"},
            "tasklist_id": {"type": "string", "description": "任务列表 ID（tasklist_guid）"},
        },
        "required": ["summary"],
    },
}

feishu_list_tasks_def = {
    "name": "feishu_list_tasks",
    "description": "查询飞书任务列表",
    "parameters": {
        "type": "object",
        "properties": {
            "completed": {"type": "boolean", "description": "筛选完成(true)/未完成(false)"},
            "page_size": {"type": "integer", "description": "每页数量，默认 50", "default": 50},
            "page_token": {"type": "string", "description": "分页标记"},
        },
    },
}

feishu_update_task_def = {
    "name": "feishu_update_task",
    "description": "更新飞书任务信息",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "任务 ID"},
            "summary": {"type": "string", "description": "新标题"},
            "description": {"type": "string", "description": "新描述"},
            "due": {"type": "string", "description": "新截止时间 ISO 8601"},
            "completed": {"type": "boolean", "description": "是否标记已完成"},
        },
        "required": ["task_id"],
    },
}

feishu_create_tasklist_def = {
    "name": "feishu_create_tasklist",
    "description": "创建飞书任务列表（任务看板/分组）",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "任务列表名称"},
        },
        "required": ["name"],
    },
}


def _parse_iso_to_timestamp(iso_str: str | None) -> int | None:
    """将 ISO 8601 字符串转为 Unix 时间戳（秒）。"""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return None


# ── 工具执行器 ──


async def feishu_create_task_handler(client: FeishuClient, args: dict) -> str:
    summary = args.get("summary") or ""
    description = args.get("description")
    due_str = args.get("due")
    members_raw = args.get("members") or []
    tasklist_id = args.get("tasklist_id")

    task_builder = InputTask.builder().summary(summary)
    if description:
        task_builder.description(description)
    if due_str:
        ts = _parse_iso_to_timestamp(due_str)
        if ts:
            task_builder.due(Due.builder().timestamp(ts).is_all_day(False).build())
    if members_raw:
        task_builder.members([
            Member.builder().id(uid).type("user").role("assignee").build()
            for uid in members_raw
        ])
    if tasklist_id:
        task_builder.tasklists([
            TaskInTasklistInfo.builder().tasklist_guid(tasklist_id).build(),
        ])

    body = task_builder.build()
    request = CreateTaskRequest.builder().request_body(body).build()

    resp = await client.client.task.v2.task.acreate(request)
    client.increment_api_count()
    err = client.check_response(resp, "feishu_create_task")
    if err:
        return client.to_json(err)

    task_obj = getattr(resp.data, "task", None)
    task_id = getattr(task_obj, "guid", None) or ""
    return client.to_json({"task_id": task_id})


async def feishu_list_tasks_handler(client: FeishuClient, args: dict) -> str:
    completed = args.get("completed")
    page_size = args.get("page_size", 50)
    page_token = args.get("page_token") or ""

    req_builder = ListTaskRequest.builder().page_size(page_size)
    if completed is not None:
        req_builder.completed(completed)
    if page_token:
        req_builder.page_token(page_token)
    request = req_builder.build()

    resp = await client.client.task.v2.task.alist(request)
    client.increment_api_count()
    err = client.check_response(resp, "feishu_list_tasks")
    if err:
        return client.to_json(err)

    body = resp.data
    tasks = []
    for t in (getattr(body, "tasks", None) or []):
        completed_at = getattr(t, "completed_at", None) or 0
        tasks.append({
            "task_id": getattr(t, "guid", None) or "",
            "summary": getattr(t, "summary", None) or "",
            "due": getattr(t, "due", None),
            "completed": bool(completed_at),
        })

    result = {
        "tasks": tasks,
        "next_page_token": getattr(body, "next_page_token", None) or "",
        "has_more": getattr(body, "has_more", False) or False,
    }
    return client.to_json(result)


async def feishu_update_task_handler(client: FeishuClient, args: dict) -> str:
    task_id = args.get("task_id") or ""
    if not task_id:
        return client.to_json({"error": "task_id is required"})

    summary = args.get("summary")
    description = args.get("description")
    due_str = args.get("due")
    completed = args.get("completed")

    task_builder = InputTask.builder()
    update_fields = []
    if summary is not None:
        task_builder.summary(summary)
        update_fields.append("summary")
    if description is not None:
        task_builder.description(description)
        update_fields.append("description")
    if due_str is not None:
        ts = _parse_iso_to_timestamp(due_str)
        if ts is not None:
            task_builder.due(Due.builder().timestamp(ts).is_all_day(False).build())
            update_fields.append("due")
    if completed is not None:
        task_builder.completed_at(int(datetime.now().timestamp()) if completed else 0)
        update_fields.append("completed_at")

    if not update_fields:
        return client.to_json({"error": "No fields to update"})

    task_body = task_builder.build()
    patch_body = PatchTaskRequestBody.builder().task(task_body).update_fields(update_fields).build()
    request = PatchTaskRequest.builder().task_guid(task_id).request_body(patch_body).build()

    resp = await client.client.task.v2.task.apatch(request)
    client.increment_api_count()
    err = client.check_response(resp, "feishu_update_task")
    if err:
        return client.to_json(err)

    task_obj = getattr(resp.data, "task", None)
    completed_at = getattr(task_obj, "completed_at", None) or 0
    result = {
        "task_id": getattr(task_obj, "guid", None) or task_id,
        "summary": getattr(task_obj, "summary", None) or "",
        "completed": bool(completed_at),
    }
    return client.to_json(result)


async def feishu_create_tasklist_handler(client: FeishuClient, args: dict) -> str:
    name = args.get("name") or ""
    if not name:
        return client.to_json({"error": "name is required"})

    body = InputTasklist.builder().name(name).build()
    request = CreateTasklistRequest.builder().request_body(body).build()

    resp = await client.client.task.v2.tasklist.acreate(request)
    client.increment_api_count()
    err = client.check_response(resp, "feishu_create_tasklist")
    if err:
        return client.to_json(err)

    tasklist_obj = getattr(resp.data, "tasklist", None)
    tasklist_id = getattr(tasklist_obj, "guid", None) or ""
    return client.to_json({"tasklist_id": tasklist_id})
