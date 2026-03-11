from core.llm.types import LLMConfig
from core.llm.services.base import BaseLLMService
from core.llm.services.openai_service import OpenAIService


def create_llm_service(config: LLMConfig) -> BaseLLMService:
    providers = {
        "openai": OpenAIService,
        "deepseek": OpenAIService,
    }

    service_cls = providers.get(config.provider)
    if service_cls is None:
        raise ValueError(
            f"Unknown LLM provider: {config.provider}. "
            f"Available: {list(providers.keys())}"
        )

    return service_cls(config)
