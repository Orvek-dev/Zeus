from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.gateway_live_delivery_runtime.support import ADAPTER_ID
from zeus_agent.gateway_live_delivery_runtime.support import build_activation
from zeus_agent.gateway_live_delivery_runtime.support import build_adapter_plan
from zeus_agent.gateway_live_delivery_runtime.support import build_transport_lease
from zeus_agent.gateway_live_delivery_runtime.support import configure_gateway
from zeus_agent.gateway_live_delivery_runtime.models import GatewayLiveDeliveryContract
from zeus_agent.gateway_live_delivery_runtime.models import GatewayLiveDeliveryDecision
from zeus_agent.gateway_live_delivery_runtime.models import GatewayLiveDeliveryScenario
from zeus_agent.live_gateway_delivery_body_runtime import LiveGatewayDeliveryBodyRuntime
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryRuntime
from zeus_agent.live_gateway_http_transport_runtime import LiveGatewayHttpTransportRuntime
from zeus_agent.live_gateway_loopback_transport_runtime import LiveGatewayLoopbackTransportRuntime
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.wave16_provider_http_server import Wave16ProviderHttpServer

_TARGET_VERSION: Final = "v1.0.0-rc.4"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.0.0-rc.4.gateway_live_delivery"


def build_gateway_live_delivery_contract(
    *,
    scenario: str = "status",
    secret_ref: str = "env://ZEUS_RC4_GATEWAY_TOKEN",
    target: str = "slack://ops",
    message: str = "Zeus gateway live delivery checkpoint",
    home: Optional[Path] = None,
) -> GatewayLiveDeliveryContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in {"status", "loopback-smoke", "blocked-target"}:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_gateway_live_delivery_scenario",),
        )
    if safe_scenario == "status":
        return _contract(decision="report", scenario="status")
    if home is not None:
        return _loopback_smoke(
            scenario=safe_scenario,
            secret_ref=secret_ref,
            target=target,
            message=message,
            home=home,
        )
    with TemporaryDirectory(prefix="zeus-rc4-gateway-") as tmp_home:
        return _loopback_smoke(
            scenario=safe_scenario,
            secret_ref=secret_ref,
            target=target,
            message=message,
            home=Path(tmp_home),
        )


def _loopback_smoke(
    *,
    scenario: str,
    secret_ref: str,
    target: str,
    message: str,
    home: Path,
) -> GatewayLiveDeliveryContract:
    settings, pairing, pairings = configure_gateway(home)
    transport_lease = build_transport_lease(network_host="127.0.0.1")
    smoke = {
        "settings": settings.to_payload(),
        "pairing": pairing.to_payload(),
        "pairings": pairings.to_payload(),
        "transport_lease": transport_lease.to_payload(),
    }
    if not target.startswith("{0}://".format(ADAPTER_ID)):
        return _contract(
            decision="blocked",
            scenario=_scenario(scenario),
            blocked_reasons=("delivery_target_not_allowlisted",),
            gateway_smoke=smoke,
        )

    secret_material = LiveSecretMaterialRuntime().check(
        transport_lease=transport_lease,
        secret_ref=secret_ref,
        allow_material_access=True,
    )
    smoke["secret_material"] = secret_material.to_payload()
    if secret_material.decision != "available":
        return _contract(
            decision="blocked",
            scenario=_scenario(scenario),
            blocked_reasons=secret_material.blocked_reasons,
            gateway_smoke=smoke,
            credential_material_accessed=secret_material.credential_material_accessed,
        )

    delivery_envelope = LiveGatewayDeliveryRuntime().prepare(
        transport_lease=transport_lease,
        secret_material=secret_material,
        adapter_id=ADAPTER_ID,
        target=target,
        message=message,
        idempotency_key="rc4-gateway-live-delivery",
    )
    smoke["delivery_envelope"] = delivery_envelope.to_payload()
    if delivery_envelope.decision != "prepared":
        return _contract(
            decision="blocked",
            scenario=_scenario(scenario),
            blocked_reasons=delivery_envelope.blocked_reasons,
            gateway_smoke=smoke,
            credential_material_accessed=secret_material.credential_material_accessed,
        )

    delivery_body = LiveGatewayDeliveryBodyRuntime().materialize(
        gateway_envelope=delivery_envelope,
        message=message,
        body_ref="gateway-body://rc4/slack/ops",
    )
    adapter_plan = build_adapter_plan(delivery_envelope)
    activation = build_activation(adapter_plan)
    loopback_execution = LiveGatewayLoopbackTransportRuntime().execute(
        activation=activation,
        adapter_plan=adapter_plan,
        gateway_envelope=delivery_envelope,
        transport_kind="loopback_delivery",
        execution_ref="gateway-live-delivery://rc4/loopback",
    )
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        execution = LiveGatewayHttpTransportRuntime().execute(
            activation=activation,
            adapter_plan=adapter_plan,
            gateway_envelope=delivery_envelope,
            delivery_endpoint="{0}/v1/chat/completions".format(server.base_url),
            transport_kind="local_http",
            execution_ref="gateway-live-delivery://rc4/http",
        )
        audit = LiveTransportAuditRuntime().audit(
            adapter_kind="gateway",
            execution=execution,
            audit_ref="live-audit://rc4/gateway-live-delivery",
        )
        redaction = LiveResponseRedactionRuntime().redact(
            audit=audit,
            response_payload=execution.redacted_response or {},
            response_ref="live-response://rc4/gateway-live-delivery",
        )
    finally:
        server.shutdown()

    ready = (
        delivery_body.decision == "materialized"
        and adapter_plan.decision == "planned"
        and activation.decision == "activation_ready"
        and loopback_execution.decision == "executed"
        and execution.decision == "executed"
        and audit.decision == "audit_ready"
        and redaction.decision == "redacted"
        and server.shutdown_complete
        and execution.non_loopback_network_opened is False
        and execution.external_delivery_opened is False
        and execution.live_production_claimed is False
    )
    smoke.update(
        {
            "delivery_body": delivery_body.to_payload(),
            "adapter_plan": adapter_plan.to_payload(),
            "activation": activation.to_payload(),
            "loopback_execution": loopback_execution.to_payload(),
            "http_execution": execution.to_payload(),
            "audit": audit.to_payload(),
            "redaction": redaction.to_payload(),
            "server_request_count": server.request_count("/v1/chat/completions"),
            "server_shutdown_complete": server.shutdown_complete,
        },
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario=_scenario(scenario),
        blocked_reasons=() if ready else tuple(execution.blocked_reasons or audit.blocked_reasons),
        gateway_smoke=smoke,
        gateway_live_delivery_ready=ready,
        network_opened=execution.network_opened,
        non_loopback_network_opened=execution.non_loopback_network_opened,
        handler_executed=execution.handler_executed,
        credential_material_accessed=secret_material.credential_material_accessed,
    )


def _contract(
    *,
    decision: GatewayLiveDeliveryDecision,
    scenario: GatewayLiveDeliveryScenario,
    blocked_reasons: tuple[str, ...] = (),
    gateway_smoke: Optional[dict[str, JsonValue]] = None,
    gateway_live_delivery_ready: bool = False,
    network_opened: bool = False,
    non_loopback_network_opened: bool = False,
    handler_executed: bool = False,
    credential_material_accessed: bool = False,
) -> GatewayLiveDeliveryContract:
    result = GatewayLiveDeliveryContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="gateway_live_delivery",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        gateway_smoke=gateway_smoke,
        gateway_live_delivery_ready=gateway_live_delivery_ready,
        production_ready=False,
        network_opened=network_opened,
        non_loopback_network_opened=non_loopback_network_opened,
        controlled_external_side_effects=False,
        handler_executed=handler_executed,
        external_delivery_opened=False,
        credential_material_accessed=credential_material_accessed,
        raw_secret_returned=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _scenario(value: str) -> GatewayLiveDeliveryScenario:
    return "blocked-target" if value == "blocked-target" else "loopback-smoke"
