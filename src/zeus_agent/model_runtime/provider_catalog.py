from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ProviderApiMode = Literal[
    "fake",
    "local",
    "openai_compatible",
    "anthropic_messages",
    "router",
    "metadata",
]


@dataclass(frozen=True)
class ProviderProfile:
    provider_id: str
    display_name: str
    api_mode: ProviderApiMode
    default_model: str
    runtime_kind: str
    network_host: str | None = None
    credential_scope: str | None = None
    local_first: bool = False
    tool_calling: bool = False
    streaming: bool = False
    structured_output: bool = False
    vision: bool = False
    embeddings: bool = False
    live_beta: bool = False

    def to_payload(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "api_mode": self.api_mode,
            "default_model": self.default_model,
            "runtime_kind": self.runtime_kind,
            "network_host": self.network_host,
            "credential_scope": self.credential_scope,
            "local_first": self.local_first,
            "tool_calling": self.tool_calling,
            "streaming": self.streaming,
            "structured_output": self.structured_output,
            "vision": self.vision,
            "embeddings": self.embeddings,
            "live_beta": self.live_beta,
        }


def provider_catalog() -> tuple[ProviderProfile, ...]:
    return (
        ProviderProfile(
            provider_id="fake",
            display_name="Deterministic Fake",
            api_mode="fake",
            default_model="fake.zeus",
            runtime_kind="fake",
            tool_calling=True,
            structured_output=True,
        ),
        ProviderProfile(
            provider_id="local-llm",
            display_name="Local LLM",
            api_mode="local",
            default_model="local.default",
            runtime_kind="local_llm",
            local_first=True,
        ),
        ProviderProfile(
            provider_id="ollama",
            display_name="Ollama",
            api_mode="openai_compatible",
            default_model="llama3.1",
            runtime_kind="local_llm",
            network_host="localhost",
            local_first=True,
            streaming=True,
        ),
        ProviderProfile(
            provider_id="llama-cpp",
            display_name="llama.cpp server",
            api_mode="openai_compatible",
            default_model="local.gguf",
            runtime_kind="local_llm",
            network_host="localhost",
            local_first=True,
        ),
        ProviderProfile(
            provider_id="vllm",
            display_name="vLLM",
            api_mode="openai_compatible",
            default_model="vllm.default",
            runtime_kind="openai_compatible",
            network_host="localhost",
            local_first=True,
            streaming=True,
            tool_calling=True,
        ),
        ProviderProfile(
            provider_id="lm-studio",
            display_name="LM Studio",
            api_mode="openai_compatible",
            default_model="local.lmstudio",
            runtime_kind="openai_compatible",
            network_host="localhost",
            local_first=True,
        ),
        ProviderProfile(
            provider_id="openai-compatible",
            display_name="Custom OpenAI-compatible",
            api_mode="openai_compatible",
            default_model="custom.default",
            runtime_kind="openai_compatible",
            credential_scope="external.openai_compatible.readonly",
            tool_calling=True,
            streaming=True,
            structured_output=True,
        ),
        ProviderProfile(
            provider_id="openai",
            display_name="OpenAI",
            api_mode="openai_compatible",
            default_model="gpt-4.1",
            runtime_kind="openai_compatible",
            network_host="api.openai.com",
            credential_scope="external.openai.readonly",
            tool_calling=True,
            streaming=True,
            structured_output=True,
            vision=True,
            embeddings=True,
        ),
        ProviderProfile(
            provider_id="anthropic",
            display_name="Anthropic",
            api_mode="anthropic_messages",
            default_model="claude-sonnet-4",
            runtime_kind="anthropic_metadata",
            network_host="api.anthropic.com",
            credential_scope="external.anthropic.readonly",
            tool_calling=True,
            streaming=True,
            vision=True,
        ),
        ProviderProfile(
            provider_id="openrouter",
            display_name="OpenRouter",
            api_mode="router",
            default_model="openrouter/auto",
            runtime_kind="openai_compatible",
            network_host="openrouter.ai",
            credential_scope="external.openrouter.readonly",
            tool_calling=True,
            streaming=True,
        ),
        ProviderProfile(
            provider_id="nous-portal",
            display_name="Nous Portal",
            api_mode="router",
            default_model="nous/auto",
            runtime_kind="openai_compatible",
            network_host="portal.nousresearch.com",
            credential_scope="external.nous.readonly",
            tool_calling=True,
        ),
        ProviderProfile(
            provider_id="gemini",
            display_name="Gemini",
            api_mode="metadata",
            default_model="gemini-pro",
            runtime_kind="anthropic_metadata",
            network_host="generativelanguage.googleapis.com",
            credential_scope="external.gemini.readonly",
            vision=True,
            structured_output=True,
        ),
        ProviderProfile(
            provider_id="huggingface",
            display_name="Hugging Face Inference",
            api_mode="openai_compatible",
            default_model="hf.default",
            runtime_kind="openai_compatible",
            network_host="api-inference.huggingface.co",
            credential_scope="external.huggingface.readonly",
        ),
        ProviderProfile(
            provider_id="nvidia-nim",
            display_name="NVIDIA NIM",
            api_mode="openai_compatible",
            default_model="nim.default",
            runtime_kind="openai_compatible",
            network_host="integrate.api.nvidia.com",
            credential_scope="external.nvidia_nim.readonly",
            streaming=True,
        ),
        ProviderProfile(
            provider_id="litellm",
            display_name="LiteLLM Proxy",
            api_mode="openai_compatible",
            default_model="litellm.default",
            runtime_kind="openai_compatible",
            network_host="localhost",
            tool_calling=True,
            streaming=True,
        ),
        ProviderProfile(
            provider_id="local-multimodal",
            display_name="Local Multimodal",
            api_mode="local",
            default_model="local.vision",
            runtime_kind="local_llm",
            local_first=True,
            vision=True,
        ),
    )


def provider_catalog_payload() -> dict[str, object]:
    profiles = provider_catalog()
    return {
        "provider_profile_count": len(profiles),
        "api_modes": sorted({profile.api_mode for profile in profiles}),
        "local_first_count": sum(1 for profile in profiles if profile.local_first),
        "tool_calling_count": sum(1 for profile in profiles if profile.tool_calling),
        "profiles": [profile.to_payload() for profile in profiles],
        "live_production_claimed": False,
    }


def get_provider_profile(provider_id: str) -> ProviderProfile:
    for profile in provider_catalog():
        if profile.provider_id == provider_id:
            return profile
    raise KeyError(provider_id)


__all__ = [
    "ProviderApiMode",
    "ProviderProfile",
    "get_provider_profile",
    "provider_catalog",
    "provider_catalog_payload",
]
