from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool.feishu.message import (
    feishu_send_message_def, feishu_send_message_handler,
    feishu_reply_message_def, feishu_reply_message_handler,
    feishu_get_message_history_def, feishu_get_message_history_handler,
)
from core.tool.feishu.doc import (
    feishu_create_document_def, feishu_create_document_handler,
    feishu_read_document_def, feishu_read_document_handler,
    feishu_read_document_blocks_def, feishu_read_document_blocks_handler,
    feishu_update_document_def, feishu_update_document_handler,
    feishu_get_document_info_def, feishu_get_document_info_handler,
)
from core.tool.feishu.bitable import (
    feishu_create_bitable_def, feishu_create_bitable_handler,
    feishu_create_bitable_table_def, feishu_create_bitable_table_handler,
    feishu_list_bitable_records_def, feishu_list_bitable_records_handler,
    feishu_create_bitable_records_def, feishu_create_bitable_records_handler,
    feishu_update_bitable_record_def, feishu_update_bitable_record_handler,
    feishu_delete_bitable_records_def, feishu_delete_bitable_records_handler,
    feishu_list_bitable_fields_def, feishu_list_bitable_fields_handler,
)
from core.tool.feishu.drive import (
    feishu_list_files_def, feishu_list_files_handler,
    feishu_create_folder_def, feishu_create_folder_handler,
    feishu_get_file_info_def, feishu_get_file_info_handler,
    feishu_get_root_folder_def, feishu_get_root_folder_handler,
)
from core.tool.feishu.task import (
    feishu_create_task_def, feishu_create_task_handler,
    feishu_list_tasks_def, feishu_list_tasks_handler,
    feishu_update_task_def, feishu_update_task_handler,
    feishu_create_tasklist_def, feishu_create_tasklist_handler,
)

if TYPE_CHECKING:
    from core.tool.feishu.client import FeishuClient
    from core.tool.manager import ToolManager


_FEISHU_TOOLS = [
    # IM Messages (3)
    (feishu_send_message_def, feishu_send_message_handler),
    (feishu_reply_message_def, feishu_reply_message_handler),
    (feishu_get_message_history_def, feishu_get_message_history_handler),
    # Cloud Documents (5)
    (feishu_create_document_def, feishu_create_document_handler),
    (feishu_read_document_def, feishu_read_document_handler),
    (feishu_read_document_blocks_def, feishu_read_document_blocks_handler),
    (feishu_update_document_def, feishu_update_document_handler),
    (feishu_get_document_info_def, feishu_get_document_info_handler),
    # Bitable (7)
    (feishu_create_bitable_def, feishu_create_bitable_handler),
    (feishu_create_bitable_table_def, feishu_create_bitable_table_handler),
    (feishu_list_bitable_records_def, feishu_list_bitable_records_handler),
    (feishu_create_bitable_records_def, feishu_create_bitable_records_handler),
    (feishu_update_bitable_record_def, feishu_update_bitable_record_handler),
    (feishu_delete_bitable_records_def, feishu_delete_bitable_records_handler),
    (feishu_list_bitable_fields_def, feishu_list_bitable_fields_handler),
    # Drive (4)
    (feishu_list_files_def, feishu_list_files_handler),
    (feishu_create_folder_def, feishu_create_folder_handler),
    (feishu_get_file_info_def, feishu_get_file_info_handler),
    (feishu_get_root_folder_def, feishu_get_root_folder_handler),
    # Tasks (4)
    (feishu_create_task_def, feishu_create_task_handler),
    (feishu_list_tasks_def, feishu_list_tasks_handler),
    (feishu_update_task_def, feishu_update_task_handler),
    (feishu_create_tasklist_def, feishu_create_tasklist_handler),
]


def register_feishu_tools(tool_manager: ToolManager, feishu_client: FeishuClient) -> None:
    """Register all 23 Feishu API tools into ToolManager."""
    for definition, handler in _FEISHU_TOOLS:
        tool_manager.register(
            name=definition["name"],
            definition=definition,
            handler=lambda args, h=handler: h(feishu_client, args),
            category="feishu",
        )
