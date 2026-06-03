from __future__ import annotations

from .models import (
    McpDispatchEnvelope,
    McpEvidenceEnvelope,
    McpFacadeEnvelope,
    McpServerManifest,
)


class McpFacade:
    def plan_manifest(self, manifest: McpServerManifest) -> McpFacadeEnvelope:
        blocked = manifest.quarantine_state == "quarantined"
        reason = (
            "mcp_manifest_quarantined;{0}".format(
                ";".join(manifest.quarantine_reasons),
            )
            if blocked
            else "mcp_manifest_pinned"
        )
        evidence = McpEvidenceEnvelope(
            server_id=manifest.server_id,
            source_ref=manifest.source_ref,
            source_pinned=manifest.source_pinned,
            trust_level=manifest.trust_level,
            tool_count=len(manifest.tools),
            quarantine_state=manifest.quarantine_state,
            quarantine_reasons=manifest.quarantine_reasons,
            prompt_injection_detected=any(
                (
                    manifest.description_prompt_injection_detected,
                    *(
                        tool.description_prompt_injection_detected
                        for tool in manifest.tools
                    ),
                ),
            ),
            secret_detected=any(
                (
                    manifest.description_secret_detected,
                    *(tool.description_secret_detected for tool in manifest.tools),
                ),
            ),
        )
        dispatch = McpDispatchEnvelope(
            server_id=manifest.server_id,
            source_ref=manifest.source_ref,
            tool_names=tuple(tool.name for tool in manifest.tools),
            capability_ids=tuple(tool.capability_id for tool in manifest.tools),
        )
        return McpFacadeEnvelope(
            decision="blocked" if blocked else "planned",
            reason=reason,
            dispatch=dispatch,
            evidence=evidence,
        )


__all__ = ["McpFacade"]
