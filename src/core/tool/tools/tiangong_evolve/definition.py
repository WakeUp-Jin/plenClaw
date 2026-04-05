"""天工锻造令工具定义。"""

from core.tool.types import InternalTool, ToolParameterSchema
from core.tool.tools.tiangong_evolve.executor import (
    tiangong_evolve_handler,
    render_evolve_result,
)

TianGongEvolveTool = InternalTool(
    name="TianGongEvolve",
    category="tiangong",
    description=(
        "向天工下达锻造令，请求锻造新的 CLI 工具。"
        "天工会在下次巡查时开始锻造（默认每 15 分钟巡查一次）。"
        "锻造完成后，新工具将出现在 TianGongToolList Skill 中，"
        "届时可通过 Bash 工具直接调用。"
        "仅在用户明确需要如意具备新的持久能力时使用。"
    ),
    parameters=ToolParameterSchema(
        type="object",
        properties={
            "task": {
                "type": "string",
                "description": (
                    "需要锻造的工具的详细描述，包括功能目标、"
                    "期望的命令行用法、输入输出格式、外部依赖等"
                ),
            },
            "tool_name": {
                "type": "string",
                "description": (
                    "工具名称（英文、短横线分隔，如 weather-tool）。"
                    "不传则自动从 task 推导"
                ),
            },
        },
        required=["task"],
    ),
    handler=tiangong_evolve_handler,
    render_result=render_evolve_result,
    is_read_only=False,
    should_confirm=True,
)
