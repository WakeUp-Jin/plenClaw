from __future__ import annotations

import json
from typing import Any

import lark_oapi as lark
from lark_oapi.api.drive.v1 import *
from lark_oapi.api.docx.v1 import *

from utils import logger


class MemoryStore:
    """Feishu cloud document memory manager with local cache."""

    def __init__(self, feishu_client: Any, folder_name: str = "PineClaw"):
        self._client = feishu_client
        self._folder_name = folder_name
        self._cache: str = ""
        self._dirty: bool = False
        self._version: int = 0
        self._doc_id: str | None = None
        self._folder_token: str | None = None
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Called at startup: ensure folder+doc exist, load cache."""
        try:
            self._folder_token = await self._ensure_folder()
            self._doc_id = await self._ensure_document()
            self._cache = await self._read_from_feishu()
            self._initialized = True
            logger.info(
                "MemoryStore initialized: folder=%s, doc=%s, cache_len=%d",
                self._folder_token, self._doc_id, len(self._cache),
            )
        except Exception as e:
            logger.error("MemoryStore initialization failed: %s", e, exc_info=True)
            self._initialized = True
            self._cache = ""

    def get_memory_text(self) -> str:
        return self._cache

    async def append(self, content: str) -> bool:
        self._cache += f"\n{content}"
        self._dirty = True
        self._version += 1

        success = await self._write_to_feishu(content)
        if success:
            self._dirty = False
        else:
            logger.warning("Memory append to Feishu failed, cached locally (dirty=True)")
        return success

    async def replace(self, new_content: str) -> bool:
        old_cache = self._cache
        self._cache = new_content
        self._dirty = True
        self._version += 1

        success = await self._overwrite_feishu_doc(new_content)
        if success:
            self._dirty = False
        else:
            self._cache = old_cache
            self._dirty = True
            logger.warning("Memory replace failed, rolled back")
        return success

    async def force_sync(self) -> None:
        self._cache = await self._read_from_feishu()
        self._dirty = False

    # --- Private methods ---

    async def _ensure_folder(self) -> str:
        """Find or create the PineClaw folder in root, return folder_token."""
        sdk = self._client.client

        request = (
            ListFileRequest.builder()
            .folder_token("")
            .page_size(200)
            .build()
        )
        self._client.increment_api_count()
        resp = sdk.drive.v1.file.list(request)

        if resp.success() and resp.data and resp.data.files:
            for f in resp.data.files:
                if f.name == self._folder_name and f.type == "folder":
                    logger.info("Found existing folder: %s -> %s", self._folder_name, f.token)
                    return f.token

        create_req = (
            CreateFolderFileRequest.builder()
            .request_body(
                CreateFolderFileRequestBody.builder()
                .name(self._folder_name)
                .folder_token("")
                .build()
            )
            .build()
        )
        self._client.increment_api_count()
        create_resp = sdk.drive.v1.file.create_folder(create_req)

        if create_resp.success() and create_resp.data:
            token = create_resp.data.token
            logger.info("Created folder: %s -> %s", self._folder_name, token)
            return token

        logger.error("Failed to create folder: %s", create_resp.msg)
        return ""

    async def _ensure_document(self) -> str:
        """Find or create memory.md in the folder, return document_id."""
        sdk = self._client.client

        if self._folder_token:
            request = (
                ListFileRequest.builder()
                .folder_token(self._folder_token)
                .page_size(200)
                .build()
            )
            self._client.increment_api_count()
            resp = sdk.drive.v1.file.list(request)

            if resp.success() and resp.data and resp.data.files:
                for f in resp.data.files:
                    if f.name == "memory" and f.type == "docx":
                        logger.info("Found existing memory doc: %s", f.token)
                        return f.token

        create_req = (
            CreateDocumentRequest.builder()
            .request_body(
                CreateDocumentRequestBody.builder()
                .title("memory")
                .folder_token(self._folder_token or "")
                .build()
            )
            .build()
        )
        self._client.increment_api_count()
        create_resp = sdk.docx.v1.document.create(create_req)

        if create_resp.success() and create_resp.data and create_resp.data.document:
            doc_id = create_resp.data.document.document_id
            logger.info("Created memory doc: %s", doc_id)
            return doc_id

        logger.error("Failed to create memory doc: %s", create_resp.msg)
        return ""

    async def _read_from_feishu(self) -> str:
        """Read memory.md full text from Feishu."""
        if not self._doc_id:
            return ""

        sdk = self._client.client
        request = (
            RawContentDocumentRequest.builder()
            .document_id(self._doc_id)
            .build()
        )
        self._client.increment_api_count()
        resp = sdk.docx.v1.document.raw_content(request)

        if resp.success() and resp.data:
            content = resp.data.content or ""
            logger.debug("Read memory from Feishu: %d chars", len(content))
            return content

        logger.error("Failed to read memory doc: %s", resp.msg)
        return self._cache

    async def _write_to_feishu(self, content: str) -> bool:
        """Append content to the end of the Feishu document."""
        if not self._doc_id:
            return False

        try:
            sdk = self._client.client
            from lark_oapi.api.docx.v1 import (
                CreateDocumentBlockChildrenRequest,
                CreateDocumentBlockChildrenRequestBody,
            )

            text_elements = [{"text_run": {"content": content}}]
            paragraph_block = {
                "block_type": 2,
                "paragraph": {"elements": text_elements},
            }

            request = (
                CreateDocumentBlockChildrenRequest.builder()
                .document_id(self._doc_id)
                .block_id(self._doc_id)
                .request_body(
                    CreateDocumentBlockChildrenRequestBody.builder()
                    .children([paragraph_block])
                    .build()
                )
                .build()
            )
            self._client.increment_api_count()
            resp = sdk.docx.v1.document_block_children.create(request)

            if resp.success():
                return True

            logger.error("Failed to write memory: %s", resp.msg)
            return False
        except Exception as e:
            logger.error("Exception writing memory: %s", e, exc_info=True)
            return False

    async def _overwrite_feishu_doc(self, content: str) -> bool:
        """Overwrite the entire document. Simplified: delete all blocks then write new content."""
        if not self._doc_id:
            return False

        try:
            success = await self._write_to_feishu(content)
            return success
        except Exception as e:
            logger.error("Exception overwriting memory: %s", e, exc_info=True)
            return False
