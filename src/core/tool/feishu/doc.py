"""
飞书云文档工具 - 5 个工具用于 AI Agent 操作飞书新版文档（docx）
"""
from __future__ import annotations

from typing import Any

import lark_oapi as lark
from lark_oapi.api.docx.v1 import (
    Block,
    CreateDocumentBlockChildrenRequestBody,
    CreateDocumentBlockChildrenRequest,
    CreateDocumentRequestBody,
    CreateDocumentRequest,
    GetDocumentRequest,
    ListDocumentBlockRequest,
    RawContentDocumentRequest,
    Text,
    TextElement,
    TextRun,
)

from core.tool.feishu.client import FeishuClient
from utils import logger

# Block type 映射: paragraph=2, heading1=3, heading2=4, heading3=5, bullet=12, ordered=13, code=14
_BLOCK_TYPE_MAP = {
    "paragraph": 2,
    "heading1": 3,
    "heading2": 4,
    "heading3": 5,
    "bullet": 12,
    "ordered": 13,
    "code": 14,
}


# ---------------------------------------------------------------------------
# Tool 1: feishu_create_document
# ---------------------------------------------------------------------------

feishu_create_document_def = {
    "name": "feishu_create_document",
    "description": "在飞书云空间中创建一个新文档",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "文档标题"},
            "folder_token": {
                "type": "string",
                "description": "目标文件夹 token，留空为根目录",
            },
        },
        "required": ["title"],
    },
}


async def feishu_create_document_handler(client: FeishuClient, args: dict) -> str:
    title = args["title"]
    folder_token = args.get("folder_token") or ""

    body_builder = CreateDocumentRequestBody.builder().title(title)
    if folder_token:
        body_builder = body_builder.folder_token(folder_token)

    request = (
        CreateDocumentRequest.builder()
        .request_body(body_builder.build())
        .build()
    )

    resp = await client.client.docx.v1.document.acreate(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_create_document")
    if err:
        return client.to_json(err)

    doc = resp.data.document
    document_id = doc.document_id
    url = f"https://feishu.cn/docx/{document_id}"

    return client.to_json({
        "document_id": document_id,
        "title": title,
        "url": url,
    })


# ---------------------------------------------------------------------------
# Tool 2: feishu_read_document
# ---------------------------------------------------------------------------

feishu_read_document_def = {
    "name": "feishu_read_document",
    "description": "获取飞书文档的纯文本内容",
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {"type": "string", "description": "文档 ID"},
        },
        "required": ["document_id"],
    },
}


async def feishu_read_document_handler(client: FeishuClient, args: dict) -> str:
    document_id = args["document_id"]

    request = (
        RawContentDocumentRequest.builder()
        .document_id(document_id)
        .build()
    )

    resp = await client.client.docx.v1.document.araw_content(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_read_document")
    if err:
        return client.to_json(err)

    content = resp.data.content or ""
    return client.to_json({"content": content})


# ---------------------------------------------------------------------------
# Tool 3: feishu_read_document_blocks
# ---------------------------------------------------------------------------

feishu_read_document_blocks_def = {
    "name": "feishu_read_document_blocks",
    "description": "获取飞书文档的完整块结构，保留格式信息",
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {"type": "string", "description": "文档 ID"},
            "page_size": {
                "type": "integer",
                "description": "每页块数量",
                "default": 500,
            },
        },
        "required": ["document_id"],
    },
}


def _simplify_block(block: Block) -> dict:
    """将 Block 转为简化的 dict，包含 block_id, block_type 和 content"""
    result: dict[str, Any] = {
        "block_id": block.block_id or "",
        "block_type": block.block_type or 0,
    }

    text_obj = None
    if block.text:
        text_obj = block.text
    elif block.heading1:
        text_obj = block.heading1
    elif block.heading2:
        text_obj = block.heading2
    elif block.heading3:
        text_obj = block.heading3
    elif block.bullet:
        text_obj = block.bullet
    elif block.ordered:
        text_obj = block.ordered
    elif block.code:
        text_obj = block.code

    if text_obj and text_obj.elements:
        parts = []
        for elem in text_obj.elements:
            if elem.text_run and elem.text_run.content:
                parts.append(elem.text_run.content)
        result["content"] = "".join(parts)
    else:
        result["content"] = ""

    return result


async def feishu_read_document_blocks_handler(client: FeishuClient, args: dict) -> str:
    document_id = args["document_id"]
    page_size = args.get("page_size", 500)

    request = (
        ListDocumentBlockRequest.builder()
        .document_id(document_id)
        .page_size(page_size)
        .build()
    )

    resp = await client.client.docx.v1.document_block.alist(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_read_document_blocks")
    if err:
        return client.to_json(err)

    items = resp.data.items or []
    blocks = [_simplify_block(b) for b in items]

    return client.to_json({
        "blocks": blocks,
        "page_token": resp.data.page_token or "",
        "has_more": resp.data.has_more or False,
    })


# ---------------------------------------------------------------------------
# Tool 4: feishu_update_document
# ---------------------------------------------------------------------------

feishu_update_document_def = {
    "name": "feishu_update_document",
    "description": "向飞书文档中追加内容块（段落、标题等）",
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {"type": "string", "description": "文档 ID"},
            "block_id": {
                "type": "string",
                "description": "父块 ID，传 document_id 表示追加到文档末尾",
            },
            "content_blocks": {
                "type": "array",
                "description": "要追加的内容块列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "block_type": {
                            "type": "string",
                            "enum": [
                                "paragraph",
                                "heading1",
                                "heading2",
                                "heading3",
                                "bullet",
                                "ordered",
                                "code",
                            ],
                        },
                        "content": {"type": "string", "description": "块的文本内容"},
                    },
                    "required": ["block_type", "content"],
                },
            },
        },
        "required": ["document_id", "block_id", "content_blocks"],
    },
}


def _build_text_with_content(content: str) -> Text:
    """构造 Text 对象，包含单个 TextRun"""
    text_run = TextRun.builder().content(content or " ").build()
    text_element = TextElement.builder().text_run(text_run).build()
    return Text.builder().elements([text_element]).build()


def _content_block_to_block(item: dict) -> Block:
    """将简化的 content_block 转为 Feishu Block"""
    block_type_str = item.get("block_type", "paragraph")
    content = item.get("content", "") or " "

    type_num = _BLOCK_TYPE_MAP.get(block_type_str, 2)
    text_obj = _build_text_with_content(content)

    builder = Block.builder().block_type(type_num)

    if block_type_str == "paragraph":
        builder = builder.text(text_obj)
    elif block_type_str == "heading1":
        builder = builder.heading1(text_obj)
    elif block_type_str == "heading2":
        builder = builder.heading2(text_obj)
    elif block_type_str == "heading3":
        builder = builder.heading3(text_obj)
    elif block_type_str == "bullet":
        builder = builder.bullet(text_obj)
    elif block_type_str == "ordered":
        builder = builder.ordered(text_obj)
    elif block_type_str == "code":
        builder = builder.code(text_obj)
    else:
        builder = builder.text(text_obj)

    return builder.build()


async def feishu_update_document_handler(client: FeishuClient, args: dict) -> str:
    document_id = args["document_id"]
    block_id = args["block_id"]
    content_blocks = args.get("content_blocks", [])

    if not content_blocks:
        return client.to_json({"error": "content_blocks 不能为空"})

    children = [_content_block_to_block(cb) for cb in content_blocks]

    body = (
        CreateDocumentBlockChildrenRequestBody.builder()
        .children(children)
        .index(-1)  # -1 表示追加到末尾
        .build()
    )

    request = (
        CreateDocumentBlockChildrenRequest.builder()
        .document_id(document_id)
        .block_id(block_id)
        .request_body(body)
        .build()
    )

    resp = await client.client.docx.v1.document_block_children.acreate(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_update_document")
    if err:
        return client.to_json(err)

    count = len(resp.data.children) if resp.data and resp.data.children else len(children)

    return client.to_json({
        "success": True,
        "count": count,
    })


# ---------------------------------------------------------------------------
# Tool 5: feishu_get_document_info
# ---------------------------------------------------------------------------

feishu_get_document_info_def = {
    "name": "feishu_get_document_info",
    "description": "获取飞书文档的基本信息（标题、创建时间等）",
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {"type": "string", "description": "文档 ID"},
        },
        "required": ["document_id"],
    },
}


async def feishu_get_document_info_handler(client: FeishuClient, args: dict) -> str:
    document_id = args["document_id"]

    request = (
        GetDocumentRequest.builder()
        .document_id(document_id)
        .build()
    )

    resp = await client.client.docx.v1.document.aget(request)
    client.increment_api_count()

    err = client.check_response(resp, "feishu_get_document_info")
    if err:
        return client.to_json(err)

    doc = resp.data.document

    result: dict[str, Any] = {
        "document_id": doc.document_id,
        "title": doc.title or "",
        "revision_id": doc.revision_id,
    }

    if hasattr(doc, "create_time") and doc.create_time is not None:
        result["create_time"] = doc.create_time
    if hasattr(doc, "update_time") and doc.update_time is not None:
        result["update_time"] = doc.update_time

    return client.to_json(result)
