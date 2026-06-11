from __future__ import annotations

import json
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.authority_compiler_runtime import AuthorityEnvelope
from zeus_agent.capability_registry_runtime import CapabilityRecord, SideEffectClass
from zeus_agent.trust_loop_runtime import Reversibility

# Plain-language templates per capability family. THE RULE: if no template
# resolves for a side-effecting capability, the action cannot be explained —
# and what cannot be explained cannot run silently (auto-escalate to ASK).
_WHAT_TEMPLATES: Final[dict[str, str]] = {
    "fs.read": "Read workspace files",
    "fs.write": "Edit or create a file",
    "terminal.run.read": "Run a read-only shell command",
    "terminal.run.local": "Run a shell command that changes local files",
    "terminal.run.package": "Install or change packages on this machine",
    "terminal.run.external": "Run a command that can reach the network or destroy data",
    "web.fetch": "Fetch external web content (treated as untrusted)",
    "agent.spawn": "Start a subagent",
    "mail.send": "Send email from your account",
    "vcs.push": "Push commits to a remote repository",
    "mcp.": "Call an external MCP tool",
    "host.tool.": "Run a host tool Zeus has no metadata for",
}

_BLAST_LABEL: Final[dict[SideEffectClass, str]] = {
    SideEffectClass.none: "local read only",
    SideEffectClass.local_write: "this machine (workspace files)",
    SideEffectClass.account_write: "your accounts / this machine's state",
    SideEffectClass.public_write: "PUBLIC — visible outside your accounts",
}

_REVERSIBILITY_LABEL: Final[dict[Reversibility, str]] = {
    Reversibility.reversible: "reversible",
    Reversibility.compensable: "compensable (undo plan needed)",
    Reversibility.irreversible: "IRREVERSIBLE",
}


def what_template_for(capability_id: str) -> Optional[str]:
    if capability_id in _WHAT_TEMPLATES:
        return _WHAT_TEMPLATES[capability_id]
    for prefix, template in _WHAT_TEMPLATES.items():
        if prefix.endswith(".") and capability_id.startswith(prefix):
            return template
    return None


def render_card(
    *,
    capability_id: str,
    args: dict[str, JsonValue],
    record: CapabilityRecord,
    reason: str,
    envelope: Optional[AuthorityEnvelope] = None,
    undo_plan_present: bool = False,
) -> str:
    """Approval card v1 — terminal-native, expert mode, five answers.

    무엇 / 어디에 / 되돌리기 / 왜 / 전례, then the graded buttons. Rendered into
    the hook's permission prompt so the human answers a real question, not a
    naked yes/no.
    """
    what = what_template_for(capability_id) or "Unexplained capability: {0}".format(capability_id)
    scope = _scope_line(capability_id, args, envelope)
    reversible = _REVERSIBILITY_LABEL[record.reversibility]
    if record.reversibility is not Reversibility.reversible:
        reversible += " · undo plan: {0}".format("yes" if undo_plan_present else "none")
    why = _why_line(capability_id, reason, envelope)
    precedent = _precedent_line(record)
    lines = [
        "[Zeus] approval needed: {0}".format(capability_id),
        "  무엇   (what)       : {0}{1}".format(what, _args_suffix(args)),
        "  어디에 (blast)      : {0}".format(scope),
        "  되돌리기 (reversible): {0}".format(reversible),
        "  왜    (why)        : {0}".format(why),
        "  전례   (precedent)  : {0}".format(precedent),
        "  응답: [1] 이번만 once · [2] 이 세션 session · [3] 더 좁게 narrower · [4] 거절 reject",
        "  standing license: `zeus approve {0} --session <session-id>`".format(capability_id),
    ]
    return "\n".join(lines)


def _args_suffix(args: dict[str, JsonValue]) -> str:
    interesting = {
        key: value
        for key, value in args.items()
        if key in {"path", "command", "url", "network_host"} and value
    }
    if not interesting:
        return ""
    rendered = json.dumps(interesting, ensure_ascii=False)
    if len(rendered) > 120:
        rendered = rendered[:117] + "..."
    return " — {0}".format(rendered)


def _scope_line(
    capability_id: str,
    args: dict[str, JsonValue],
    envelope: Optional[AuthorityEnvelope],
) -> str:
    if envelope is not None:
        grant = envelope.grant_for(capability_id)
        if grant is not None:
            scopes = list(grant.path_scopes) + list(grant.network_hosts)
            if scopes:
                return "envelope scope: {0}".format(", ".join(scopes))
    host = args.get("network_host")
    if isinstance(host, str) and host:
        return "network host: {0}".format(host)
    path = args.get("path")
    if isinstance(path, str) and path:
        return "path: {0}".format(path)
    return "unscoped (no envelope grant)"


def _why_line(capability_id: str, reason: str, envelope: Optional[AuthorityEnvelope]) -> str:
    if envelope is not None:
        grant = envelope.grant_for(capability_id)
        if grant is not None:
            return "objective {0} → clause {1} ({2})".format(
                envelope.objective_id, grant.provenance, reason
            )
    return "host requested outside any objective envelope ({0})".format(reason)


def _precedent_line(record: CapabilityRecord) -> str:
    if not record.trust.measured:
        return "no measured history (first governed use)"
    return "trust {0:.2f} over {1} runs ({2:.0%} success)".format(
        record.trust.score, record.trust.runs, record.trust.success_rate
    )
