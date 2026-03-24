""" ListFiles 工具定义 """
from core.tool.types import InternalTool, ToolParameterSchema
from core.tool.tools.list_files.executor import list_files_handler, render_list_files_result


ListFilesTool=InternalTool(
    name="ListFiles",
    category="filesystem",
    description="列出指定文件夹下的所有文件和子文件夹",
    parameters=ToolParameterSchema(
        type="object",
        properties={
            "folder_path": {
                "type": "string", 
                "description": "文件夹路径",
            },
        },
        required=["folder_path"],
    ),
    handler=list_files_handler,
    render_result=render_list_files_result,
    is_read_only=True,
    should_confirm=False,
)