"""飞书云空间工具：列出文件、创建文件夹、获取文件信息、获取根目录。"""

from __future__ import annotations

import json
from typing import Any

import lark_oapi as lark
from lark_oapi.api.drive.v1 import *

from core.tool.feishu.client import FeishuClient
from utils import logger

# ── 工具定义 ──

feishu_list_files_def = {
    "name": "feishu_list_files",
    "description": "列出飞书云空间指定文件夹下的文件和子文件夹（类似 ls 命令）",
    "parameters": {
        "type": "object",
        "properties": {
            "folder_token": {"type": "string", "description": "文件夹 token，留空表示根目录"},
            "page_size": {"type": "integer", "description": "每页数量，默认 50，最大 200", "default": 50},
            "page_token": {"type": "string", "description": "分页标记"},
        },
    },
}

feishu_create_folder_def = {
    "name": "feishu_create_folder",
    "description": "在飞书云空间创建新文件夹",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "文件夹名称"},
            "folder_token": {"type": "string", "description": "父文件夹 token，留空为根目录"},
        },
        "required": ["name"],
    },
}

feishu_get_file_info_def = {
    "name": "feishu_get_file_info",
    "description": "获取飞书云空间中单个文件或文件夹的详细信息",
    "parameters": {
        "type": "object",
        "properties": {
            "file_token": {"type": "string", "description": "文件或文件夹的 token"},
        },
        "required": ["file_token"],
    },
}

feishu_get_root_folder_def = {
    "name": "feishu_get_root_folder",
    "description": "获取飞书云空间根目录的 token",
    "parameters": {"type": "object", "properties": {}},
}


def _doc_type_from_token(token: str) -> str:
    """根据 token 前缀推测 doc_type。"""
    if not token:
        return "doc"
    t = token.lower()
    if t.startswith("fld"):
        return "folder"
    if t.startswith("dox") or t.startswith("doc"):
        return "docx"
    if t.startswith("sht"):
        return "sheet"
    if t.startswith("bas"):
        return "bitable"
    return "doc"


# ── 工具执行器 ──


async def feishu_list_files_handler(client: FeishuClient, args: dict) -> str:
    folder_token = args.get("folder_token") or ""
    page_size = args.get("page_size", 50)
    page_token = args.get("page_token") or ""

    req_builder = ListFileRequest.builder()
    if folder_token:
        req_builder.folder_token(folder_token)
    req_builder.page_size(min(page_size, 200))
    if page_token:
        req_builder.page_token(page_token)
    request = req_builder.build()

    resp = await client.client.drive.v1.file.alist(request)
    client.increment_api_count()
    err = client.check_response(resp, "feishu_list_files")
    if err:
        return client.to_json(err)

    body = resp.data
    if not body:
        return client.to_json({"files": [], "next_page_token": "", "has_more": False})

    files = []
    for f in (body.files or []):
        files.append({
            "name": getattr(f, "name", None) or "",
            "type": getattr(f, "type", None) or "",
            "token": getattr(f, "token", None) or "",
        })

    result = {
        "files": files,
        "next_page_token": getattr(body, "next_page_token", None) or "",
        "has_more": getattr(body, "has_more", False) or False,
    }
    return client.to_json(result)


async def feishu_create_folder_handler(client: FeishuClient, args: dict) -> str:
    name = args.get("name") or ""
    folder_token = args.get("folder_token") or ""

    body_builder = CreateFolderFileRequestBody.builder().name(name)
    if folder_token:
        body_builder.folder_token(folder_token)
    body = body_builder.build()

    request = CreateFolderFileRequest.builder().request_body(body).build()

    resp = await client.client.drive.v1.file.acreate_folder(request)
    client.increment_api_count()
    err = client.check_response(resp, "feishu_create_folder")
    if err:
        return client.to_json(err)

    resp_body = resp.data
    token = getattr(resp_body, "token", None) or ""
    url = getattr(resp_body, "url", None) or ""
    return client.to_json({"folder_token": token, "url": url})


async def feishu_get_file_info_handler(client: FeishuClient, args: dict) -> str:
    file_token = args.get("file_token") or ""
    if not file_token:
        return client.to_json({"error": "file_token is required"})

    doc_type = _doc_type_from_token(file_token)
    request_doc = RequestDoc.builder().doc_token(file_token).doc_type(doc_type).build()
    meta_req = MetaRequest.builder().request_docs([request_doc]).with_url(True).build()
    request = BatchQueryMetaRequest.builder().request_body(meta_req).build()

    resp = await client.client.drive.v1.meta.abatch_query(request)
    client.increment_api_count()
    err = client.check_response(resp, "feishu_get_file_info")
    if err:
        return client.to_json(err)

    body = resp.data
    metas = getattr(body, "metas", None) or []
    if not metas:
        return client.to_json({"error": "File not found or no meta returned"})

    meta = metas[0]
    result = {
        "name": getattr(meta, "title", None) or "",
        "type": getattr(meta, "doc_type", None) or "",
        "url": getattr(meta, "url", None) or "",
    }
    return client.to_json(result)


async def feishu_get_root_folder_handler(client: FeishuClient, args: dict) -> str:
    return client.to_json({
        "root_folder_token": "",
        "hint": "Use feishu_list_files with empty folder_token to list root directory",
    })
