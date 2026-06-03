from __future__ import annotations

from .models import (
    WebResearchDispatch,
    WebResearchEnvelope,
    WebResearchEvidence,
    WebSourcePin,
)


class WebResearchFacade:
    def plan_source(self, source: WebSourcePin) -> WebResearchEnvelope:
        reasons = _web_block_reasons(source)
        evidence = WebResearchEvidence(
            source_id=source.source_id,
            source_url=source.source_url,
            source_ref=source.source_ref,
            source_pinned=source.source_pinned,
            summary=source.summary,
            secret_fields=source.secret_fields,
        )
        dispatch = WebResearchDispatch(
            source_id=source.source_id,
            source_ref=source.source_ref,
        )
        return WebResearchEnvelope(
            decision="blocked" if reasons else "planned",
            reason=";".join(reasons) if reasons else "web_source_pinned",
            dispatch=dispatch,
            evidence=evidence,
        )


def _web_block_reasons(source: WebSourcePin) -> tuple[str, ...]:
    reasons: list[str] = []
    if not source.source_pinned:
        reasons.append("web_source_unpinned")
    if source.source_ref is None:
        reasons.append("web_source_ref_missing")
    if "summary" in source.secret_fields:
        reasons.append("secret_like_summary")
    metadata_fields = {"source_id", "source_url", "source_ref"}
    if any(field in metadata_fields for field in source.secret_fields):
        reasons.append("secret_like_source_metadata")
    return tuple(reasons)


__all__ = ["WebResearchFacade"]
