from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict

TRANSPORT_PRODUCT_NAME: Final[str] = "Mercury"
INTERNAL_TRANSPORT_ALIASES: Final[tuple[str, ...]] = ()
TECHNICAL_RUNTIME_NAMES: Final[tuple[str, ...]] = (
    "objective_runtime",
    "runtime_lease",
    "security_runtime",
    "model_runtime",
    "provider_runtime",
    "tool_runtime",
    "connector_runtime",
    "gateway_runtime",
    "research_runtime",
    "ontology_runtime",
    "orchestration_runtime",
    "verification_runtime",
    "skill_evolution",
    "transport_runtime",
    "workloop_runtime",
    "product_runtime",
)
FORBIDDEN_ALIASES: Final[tuple[str, ...]] = (
    "Hermes Runtime",
    "Hermes Transport",
    "hermes_transport",
    "Dionysus Production Mode",
    "Ares Executor",
)


class ProductDomainLanguageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product_name: str
    technical_anchors: tuple[str, ...]


class CoreDomainLanguageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_count: int
    pillars: tuple[str, ...]
    mappings: tuple[ProductDomainLanguageEntry, ...]
    technical_runtime_names: tuple[str, ...]
    transport_product_name: str
    hermes_name_reserved: bool
    technical_runtime_names_preserved: bool
    internal_transport_aliases: tuple[str, ...]
    forbidden_aliases: tuple[str, ...]


class CoreDomainLanguage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mappings: tuple[ProductDomainLanguageEntry, ...]
    technical_runtime_names: tuple[str, ...]
    forbidden_aliases: tuple[str, ...]

    def product_names(self) -> tuple[str, ...]:
        return tuple(entry.product_name for entry in self.mappings)

    def anchors_for(self, product_name: str) -> tuple[str, ...]:
        for entry in self.mappings:
            if entry.product_name == product_name:
                return entry.technical_anchors
        raise KeyError(product_name)

    def rejects_alias(self, alias: str) -> bool:
        return alias in self.forbidden_aliases

    def summary(self) -> CoreDomainLanguageSummary:
        runtime_names = set(self.technical_runtime_names)
        return CoreDomainLanguageSummary(
            canonical_count=len(self.mappings),
            pillars=self.product_names(),
            mappings=self.mappings,
            technical_runtime_names=self.technical_runtime_names,
            transport_product_name=TRANSPORT_PRODUCT_NAME,
            hermes_name_reserved=True,
            technical_runtime_names_preserved=all(
                runtime_name in runtime_names
                for runtime_name in TECHNICAL_RUNTIME_NAMES
            ),
            internal_transport_aliases=INTERNAL_TRANSPORT_ALIASES,
            forbidden_aliases=self.forbidden_aliases,
        )


CORE_DOMAIN_LANGUAGE: Final[CoreDomainLanguage] = CoreDomainLanguage(
    mappings=(
        ProductDomainLanguageEntry(
            product_name="Zeus Kernel",
            technical_anchors=(
                "kernel",
                "objective_runtime",
                "verification_runtime",
                "evidence/authority center",
            ),
        ),
        ProductDomainLanguageEntry(
            product_name="Athena",
            technical_anchors=("objective_runtime", "objective reasoning/goal contracts"),
        ),
        ProductDomainLanguageEntry(
            product_name="Thunderbolt",
            technical_anchors=("runtime_lease", "capability authority/dispatch grants"),
        ),
        ProductDomainLanguageEntry(
            product_name="Aegis",
            technical_anchors=(
                "security_runtime",
                "approval",
                "lease",
                "sandbox",
                "fail-closed policy",
            ),
        ),
        ProductDomainLanguageEntry(
            product_name="Mercury",
            technical_anchors=(
                "transport_runtime",
                "connector_runtime",
                "mcp/api/gateway routing",
            ),
        ),
        ProductDomainLanguageEntry(
            product_name="Apollo",
            technical_anchors=(
                "model_runtime",
                "provider_runtime",
                "inference",
                "eval",
            ),
        ),
        ProductDomainLanguageEntry(
            product_name="Hephaestus",
            technical_anchors=("tool_runtime", "tool execution/build adapters"),
        ),
        ProductDomainLanguageEntry(
            product_name="Poseidon",
            technical_anchors=("gateway_runtime", "external delivery/surface containment"),
        ),
        ProductDomainLanguageEntry(
            product_name="Artemis",
            technical_anchors=(
                "research_runtime",
                "source pins",
                "web",
                "GitHub evidence",
            ),
        ),
        ProductDomainLanguageEntry(
            product_name="Demeter",
            technical_anchors=("ontology_runtime", "state", "durable knowledge"),
        ),
        ProductDomainLanguageEntry(
            product_name="Olympus",
            technical_anchors=("orchestration_runtime", "workloop coordination"),
        ),
        ProductDomainLanguageEntry(
            product_name="Prometheus",
            technical_anchors=("skill_evolution", "reviewed self-improvement"),
        ),
    ),
    technical_runtime_names=TECHNICAL_RUNTIME_NAMES,
    forbidden_aliases=FORBIDDEN_ALIASES,
)


def core_domain_language_summary() -> CoreDomainLanguageSummary:
    return CORE_DOMAIN_LANGUAGE.summary()
