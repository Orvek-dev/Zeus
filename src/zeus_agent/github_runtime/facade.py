from __future__ import annotations

from .models import (
    GitHubResearchDispatch,
    GitHubResearchEnvelope,
    GitHubResearchEvidence,
    GitHubSourcePin,
)


class GitHubResearchFacade:
    def plan_source(self, source: GitHubSourcePin) -> GitHubResearchEnvelope:
        reasons = _github_block_reasons(source)
        evidence = GitHubResearchEvidence(
            repo=source.repo,
            ref=source.ref,
            query=source.query,
            query_evidence_id=source.query_evidence_id,
            source_pinned=source.source_pinned,
            freshness=source.freshness,
            summary=source.summary,
            secret_fields=source.secret_fields,
        )
        dispatch = GitHubResearchDispatch(
            repo=source.repo,
            ref=source.ref,
            query_evidence_id=source.query_evidence_id,
        )
        return GitHubResearchEnvelope(
            decision="blocked" if reasons else "planned",
            reason=";".join(reasons) if reasons else "github_source_pinned",
            dispatch=dispatch,
            evidence=evidence,
        )


def _github_block_reasons(source: GitHubSourcePin) -> tuple[str, ...]:
    reasons: list[str] = []
    if not source.source_pinned:
        reasons.append("github_source_unpinned")
    if source.freshness == "stale":
        reasons.append("github_source_stale")
    if source.ref is None:
        reasons.append("github_ref_missing")
    if source.query_evidence_id is None:
        reasons.append("github_query_evidence_missing")
    if "query" in source.secret_fields:
        reasons.append("secret_like_query")
    if "summary" in source.secret_fields:
        reasons.append("secret_like_summary")
    metadata_fields = {"repo", "ref", "query_evidence_id"}
    if any(field in metadata_fields for field in source.secret_fields):
        reasons.append("secret_like_github_source_metadata")
    return tuple(reasons)


__all__ = ["GitHubResearchFacade"]
