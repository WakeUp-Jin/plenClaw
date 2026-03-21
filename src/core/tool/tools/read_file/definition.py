"""ReadFile 工具定义。"""

from core.tool.types import InternalTool, ToolParameterSchema
from core.tool.tools.read_file.executor import read_file_handler, render_read_file_result

ReadFileTool = InternalTool(
    name="ReadFile",
    category="filesystem",
    description=(
        "读取指定文件的内容。支持通过 offset 和 limit 分页读取大文件。"
        "输出带行号前缀，便于引用。"
    ),
    parameters=ToolParameterSchema(
        type="object",
        properties={
            "file_path": {
                "type": "string",
                "description": "要读取的文件的绝对路径或相对路径",
            },
            "offset": {
                "type": "number",
                "description": "从第几行开始读取（1-indexed），默认为 1",
            },
            "limit": {
                "type": "number",
                "description": "读取多少行，默认读取全部",
            },
        },
        required=["file_path"],
    ),
    handler=read_file_handler,
    render_result=render_read_file_result,
    is_read_only=True,
    should_confirm=False,
)
