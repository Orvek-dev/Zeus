from __future__ import annotations

import json

import zeus_agent.product_runtime as product_runtime
from zeus_agent.product_runtime import final_core_contracts_payload
from zeus_agent.product_runtime.domain_language import core_domain_language_summary


EXPECTED_PRODUCT_NAMES = (
    "Zeus Kernel",
    "Athena",
    "Thunderbolt",
    "Aegis",
    "Mercury",
    "Apollo",
    "Hephaestus",
    "Poseidon",
    "Artemis",
    "Demeter",
    "Olympus",
    "Prometheus",
)

REQUIRED_TECHNICAL_RUNTIME_NAMES = {
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
}


def test_core_domain_language_summary_reports_canonical_count_and_alias_contract() -> None:
    # Given: the shared product schema summarizes the approved core language.
    summary = core_domain_language_summary()
    forbidden_aliases = {
        "Hermes Runtime",
        "Hermes Transport",
        "hermes_transport",
        "Dionysus Production Mode",
        "Ares Executor",
    }

    # When / Then: the summary exposes the canonical count and alias boundaries.
    assert summary.canonical_count == 12
    assert summary.transport_product_name == "Mercury"
    assert summary.hermes_name_reserved is True
    assert summary.technical_runtime_names_preserved is True
    assert forbidden_aliases <= set(summary.forbidden_aliases)
    assert summary.internal_transport_aliases == ()


def test_core_domain_language_mapping_is_reduced_and_stable(tmp_path) -> None:
    # Given: the final product runtime emits the canonical Zeus core contract.
    raw_secret = "ghp_DOMAIN_LANGUAGE_FIXTURE"
    language = getattr(product_runtime, "CORE_DOMAIN_LANGUAGE", None)

    # When: the mapping and snapshot payload are inspected as JSON-compatible data.
    payload = final_core_contracts_payload(
        objective="Implement final Zeus architecture with stable product language.",
        raw_secret=raw_secret,
        evidence_root=tmp_path,
    )
    core_language = payload.get("core_domain_language")
    serialized = json.dumps(payload, sort_keys=True)

    # Then: only the approved 12 product pillars are exposed with required runtimes.
    assert language is not None, "CORE_DOMAIN_LANGUAGE must be exported"
    assert language.product_names() == EXPECTED_PRODUCT_NAMES
    assert core_language is not None, "ProductRuntimeSnapshot must serialize core_domain_language"
    assert tuple(core_language["pillars"]) == EXPECTED_PRODUCT_NAMES
    assert "product_names" not in core_language
    assert len(core_language["mappings"]) == 12
    assert {
        name
        for item in core_language["mappings"]
        for name in item["technical_anchors"]
        if name in REQUIRED_TECHNICAL_RUNTIME_NAMES
    } >= REQUIRED_TECHNICAL_RUNTIME_NAMES - {"workloop_runtime", "product_runtime"}
    assert set(core_language["technical_runtime_names"]) >= REQUIRED_TECHNICAL_RUNTIME_NAMES
    assert core_language["transport_product_name"] == "Mercury"
    assert core_language["hermes_name_reserved"] is True
    assert core_language["technical_runtime_names_preserved"] is True
    assert "Hermes" not in core_language["internal_transport_aliases"]
    assert raw_secret not in serialized


def test_domain_language_rejects_hermes_transport_and_overmapping(tmp_path) -> None:
    # Given: Zeus core language must preserve Mercury as transport/runtime naming.
    language = getattr(product_runtime, "CORE_DOMAIN_LANGUAGE", None)
    payload = final_core_contracts_payload(
        objective="Implement final Zeus architecture without Hermes transport aliases.",
        raw_secret="sk-domain-language-secret",
        evidence_root=tmp_path,
    )

    # When: forbidden aliases and adjacent myth names are checked.
    core_language = payload.get("core_domain_language")
    forbidden_aliases = (
        "Hermes Runtime",
        "Hermes Transport",
        "hermes_transport",
        "Dionysus Production Mode",
        "Ares Executor",
    )
    pillars = tuple(core_language["pillars"]) if core_language else ()

    # Then: Hermes transport aliases and unapproved myth pillars stay rejected.
    assert language is not None, "CORE_DOMAIN_LANGUAGE must be exported"
    assert all(language.rejects_alias(alias) for alias in forbidden_aliases)
    assert all(alias in core_language["forbidden_aliases"] for alias in forbidden_aliases)
    assert language.anchors_for("Mercury") == (
        "transport_runtime",
        "connector_runtime",
        "mcp/api/gateway routing",
    )
    assert not any("Hermes" in anchor for anchor in language.anchors_for("Mercury"))
    assert "Hermes" not in pillars
    assert "Dionysus" not in pillars
    assert "Ares" not in pillars
