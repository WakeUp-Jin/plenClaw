"""飞书多维表格 (Bitable) 工具 - 7 个工具供 AI Agent 调用"""

from __future__ import annotations

import json
from typing import Any

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    AppTableCreateHeader,
    AppTableRecord,
    BatchCreateAppTableRecordRequestBody,
    BatchCreateAppTableRecordRequest,
    BatchDeleteAppTableRecordRequestBody,
    BatchDeleteAppTableRecordRequest,
    CreateAppRequest,
    CreateAppTableRequestBody,
    CreateAppTableRequest,
    ListAppTableFieldRequest,
    ListAppTableRecordRequest,
    ReqApp,
    ReqTable,
    UpdateAppTableRecordRequest,
)

from core.tool.feishu.client import FeishuClient
from utils import logger


# ---------------------------------------------------------------------------
# Tool 1: feishu_create_bitable
# ---------------------------------------------------------------------------

feishu_create_bitable_def = {
    "name": "feishu_create_bitable",
    "description": "创建一个新的飞书多维表格",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "多维表格名称"},
            "folder_token": {"type": "string", "description": "目标文件夹 token，可选"},
        },
        "required": ["name"],
    },
}


async def feishu_create_bitable_handler(client: FeishuClient, args: dict) -> str:
    name = args["name"]
    folder_token = args.get("folder_token")

    body_builder = ReqApp.builder().name(name)
    if folder_token is not None:
        body_builder = body_builder.folder_token(folder_token)
    request = CreateAppRequest.builder().request_body(body_builder.build()).build()

    resp = await client.client.bitable.v1.app.acreate(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_create_bitable")
    if err:
        return client.to_json(err)

    result = {
        "app_token": resp.data.app.app_token,
        "url": getattr(resp.data.app, "url", None) or "",
    }
    return client.to_json(result)


# ---------------------------------------------------------------------------
# Tool 2: feishu_create_bitable_table
# ---------------------------------------------------------------------------

feishu_create_bitable_table_def = {
    "name": "feishu_create_bitable_table",
    "description": "在多维表格中创建数据表，同时定义字段结构",
    "parameters": {
        "type": "object",
        "properties": {
            "app_token": {"type": "string", "description": "多维表格 app_token"},
            "name": {"type": "string", "description": "数据表名称"},
            "fields": {
                "type": "array",
                "description": "字段定义，type: 1=文本 2=数字 3=单选 4=多选 5=日期 7=复选框",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_name": {"type": "string"},
                        "type": {
                            "type": "integer",
                            "description": "1=text 2=number 3=single_select 4=multi_select 5=date 7=checkbox",
                        },
                    },
                    "required": ["field_name", "type"],
                },
            },
        },
        "required": ["app_token", "name", "fields"],
    },
}


async def feishu_create_bitable_table_handler(client: FeishuClient, args: dict) -> str:
    app_token = args["app_token"]
    name = args["name"]
    fields_data = args["fields"]

    req_fields = [
        AppTableCreateHeader.builder()
        .field_name(f["field_name"])
        .type(f["type"])
        .build()
        for f in fields_data
    ]
    table = ReqTable.builder().name(name).fields(req_fields).build()

    request = (
        CreateAppTableRequest.builder()
        .app_token(app_token)
        .request_body(CreateAppTableRequestBody.builder().table(table).build())
        .build()
    )

    resp = await client.client.bitable.v1.app_table.acreate(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_create_bitable_table")
    if err:
        return client.to_json(err)

    result = {"table_id": resp.data.table_id}
    return client.to_json(result)


# ---------------------------------------------------------------------------
# Tool 3: feishu_list_bitable_records
# ---------------------------------------------------------------------------

feishu_list_bitable_records_def = {
    "name": "feishu_list_bitable_records",
    "description": "查询多维表格数据表的记录，支持筛选和分页",
    "parameters": {
        "type": "object",
        "properties": {
            "app_token": {"type": "string", "description": "多维表格 app_token"},
            "table_id": {"type": "string", "description": "数据表 ID"},
            "filter": {"type": "string", "description": "筛选条件"},
            "sort": {"type": "string", "description": "排序条件"},
            "page_size": {
                "type": "integer",
                "description": "每页数量，默认 20，最大 500",
                "default": 20,
            },
            "page_token": {"type": "string", "description": "分页标记"},
        },
        "required": ["app_token", "table_id"],
    },
}


async def feishu_list_bitable_records_handler(client: FeishuClient, args: dict) -> str:
    app_token = args["app_token"]
    table_id = args["table_id"]
    page_size = args.get("page_size", 20)
    filter_str = args.get("filter")
    sort_str = args.get("sort")
    page_token = args.get("page_token")

    builder = (
        ListAppTableRecordRequest.builder()
        .app_token(app_token)
        .table_id(table_id)
        .page_size(page_size)
    )
    if filter_str is not None:
        builder = builder.filter(filter_str)
    if sort_str is not None:
        builder = builder.sort(sort_str)
    if page_token is not None:
        builder = builder.page_token(page_token)

    request = builder.build()
    resp = await client.client.bitable.v1.app_table_record.alist(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_list_bitable_records")
    if err:
        return client.to_json(err)

    records = [
        {"record_id": r.record_id, "fields": dict(r.fields) if r.fields else {}}
        for r in (resp.data.items or [])
    ]
    result = {
        "records": records,
        "has_more": getattr(resp.data, "has_more", False),
        "page_token": getattr(resp.data, "page_token", "") or "",
    }
    return client.to_json(result)


# ---------------------------------------------------------------------------
# Tool 4: feishu_create_bitable_records
# ---------------------------------------------------------------------------

feishu_create_bitable_records_def = {
    "name": "feishu_create_bitable_records",
    "description": "向多维表格数据表批量新增记录",
    "parameters": {
        "type": "object",
        "properties": {
            "app_token": {"type": "string", "description": "多维表格 app_token"},
            "table_id": {"type": "string", "description": "数据表 ID"},
            "records": {
                "type": "array",
                "description": "记录列表，每项含 fields 属性",
                "items": {
                    "type": "object",
                    "properties": {"fields": {"type": "object"}},
                    "required": ["fields"],
                },
            },
        },
        "required": ["app_token", "table_id", "records"],
    },
}


async def feishu_create_bitable_records_handler(client: FeishuClient, args: dict) -> str:
    app_token = args["app_token"]
    table_id = args["table_id"]
    records_data = args["records"]

    record_list = [
        AppTableRecord.builder().fields(r["fields"]).build() for r in records_data
    ]
    request_body = BatchCreateAppTableRecordRequestBody.builder().records(record_list).build()

    request = (
        BatchCreateAppTableRecordRequest.builder()
        .app_token(app_token)
        .table_id(table_id)
        .request_body(request_body)
        .build()
    )

    resp = await client.client.bitable.v1.app_table_record.abatch_create(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_create_bitable_records")
    if err:
        return client.to_json(err)

    record_ids = [r.record_id for r in (resp.data.records or [])]
    result = {"record_ids": record_ids}
    return client.to_json(result)


# ---------------------------------------------------------------------------
# Tool 5: feishu_update_bitable_record
# ---------------------------------------------------------------------------

feishu_update_bitable_record_def = {
    "name": "feishu_update_bitable_record",
    "description": "更新多维表格中的一条记录",
    "parameters": {
        "type": "object",
        "properties": {
            "app_token": {"type": "string", "description": "多维表格 app_token"},
            "table_id": {"type": "string", "description": "数据表 ID"},
            "record_id": {"type": "string", "description": "记录 ID"},
            "fields": {"type": "object", "description": "要更新的字段名到值的映射"},
        },
        "required": ["app_token", "table_id", "record_id", "fields"],
    },
}


async def feishu_update_bitable_record_handler(client: FeishuClient, args: dict) -> str:
    app_token = args["app_token"]
    table_id = args["table_id"]
    record_id = args["record_id"]
    fields = args["fields"]

    request = (
        UpdateAppTableRecordRequest.builder()
        .app_token(app_token)
        .table_id(table_id)
        .record_id(record_id)
        .request_body(AppTableRecord.builder().fields(fields).build())
        .build()
    )

    resp = await client.client.bitable.v1.app_table_record.aupdate(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_update_bitable_record")
    if err:
        return client.to_json(err)

    rec = resp.data.record
    result = {
        "record_id": rec.record_id,
        "fields": dict(rec.fields) if rec.fields else {},
    }
    return client.to_json(result)


# ---------------------------------------------------------------------------
# Tool 6: feishu_delete_bitable_records
# ---------------------------------------------------------------------------

feishu_delete_bitable_records_def = {
    "name": "feishu_delete_bitable_records",
    "description": "批量删除多维表格中的记录",
    "parameters": {
        "type": "object",
        "properties": {
            "app_token": {"type": "string", "description": "多维表格 app_token"},
            "table_id": {"type": "string", "description": "数据表 ID"},
            "record_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要删除的记录 ID 列表",
            },
        },
        "required": ["app_token", "table_id", "record_ids"],
    },
}


async def feishu_delete_bitable_records_handler(client: FeishuClient, args: dict) -> str:
    app_token = args["app_token"]
    table_id = args["table_id"]
    record_ids = args["record_ids"]

    request_body = BatchDeleteAppTableRecordRequestBody.builder().records(record_ids).build()

    request = (
        BatchDeleteAppTableRecordRequest.builder()
        .app_token(app_token)
        .table_id(table_id)
        .request_body(request_body)
        .build()
    )

    resp = await client.client.bitable.v1.app_table_record.abatch_delete(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_delete_bitable_records")
    if err:
        return client.to_json(err)

    result = {"success": True, "deleted_count": len(record_ids)}
    return client.to_json(result)


# ---------------------------------------------------------------------------
# Tool 7: feishu_list_bitable_fields
# ---------------------------------------------------------------------------

feishu_list_bitable_fields_def = {
    "name": "feishu_list_bitable_fields",
    "description": "列出多维表格数据表的所有字段定义",
    "parameters": {
        "type": "object",
        "properties": {
            "app_token": {"type": "string", "description": "多维表格 app_token"},
            "table_id": {"type": "string", "description": "数据表 ID"},
        },
        "required": ["app_token", "table_id"],
    },
}


async def feishu_list_bitable_fields_handler(client: FeishuClient, args: dict) -> str:
    app_token = args["app_token"]
    table_id = args["table_id"]

    request = (
        ListAppTableFieldRequest.builder()
        .app_token(app_token)
        .table_id(table_id)
        .build()
    )

    resp = await client.client.bitable.v1.app_table_field.alist(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_list_bitable_fields")
    if err:
        return client.to_json(err)

    fields = [
        {
            "field_id": f.field_id,
            "field_name": f.field_name,
            "type": f.type,
        }
        for f in (resp.data.items or [])
    ]
    result = {"fields": fields}
    return client.to_json(result)
