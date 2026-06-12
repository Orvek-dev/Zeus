from __future__ import annotations

from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.capability_registry_runtime import CapabilityRecord, SideEffectClass
from zeus_agent.trust_loop_runtime import Reversibility

# family → (무엇을, 어디에) plain-Korean fragments. Families are capability-id
# prefixes; coverage is deliberately explicit — an unlisted family has no
# template and therefore escalates.
_FAMILY_WHAT: Final[dict[str, tuple[str, str]]] = {
    "fs.read": ("작업 폴더의 파일을 읽습니다", "내 컴퓨터의 해당 파일"),
    "fs.write": ("작업 폴더의 파일을 만들거나 수정합니다", "내 컴퓨터의 해당 파일"),
    "terminal.run.read": ("읽기 전용 셸 명령을 실행합니다", "내 컴퓨터(변경 없음)"),
    "terminal.run.local": ("로컬 파일을 바꾸는 명령을 실행합니다", "내 컴퓨터의 작업 폴더"),
    "terminal.run.package": ("패키지/환경을 설치·변경합니다", "내 개발 환경"),
    "terminal.run.external": ("네트워크/파괴적이거나 분류 불가한 명령을 실행합니다", "내 컴퓨터와 외부 시스템"),
    "web.fetch": ("웹 페이지나 검색 결과를 가져옵니다(외부 텍스트는 신뢰하지 않음)", "외부 웹사이트(읽기)"),
    "llm.generate": ("AI 모델을 호출합니다(비용 발생)", "모델 제공자(대화 내용 전송)"),
    "llm.model_switch": ("정책이 승인한 대체 모델로 요청을 바꿉니다", "이번 요청의 모델 선택"),
    "msg.send": ("메시지/메일을 보냅니다", "외부 수신자(되돌릴 수 없는 발신)"),
    "mail.send": ("메일을 보냅니다", "외부 수신자(되돌릴 수 없는 발신)"),
    "mcp.": ("외부 MCP 도구를 호출합니다", "해당 MCP 서버가 다루는 시스템"),
    "memory.write": ("에이전트 장기 기억에 내용을 저장합니다", "이후 모든 세션의 판단 근거"),
    "agent.memory.write": ("에이전트 장기 기억 후보를 저장합니다", "이후 세션의 판단 근거 후보"),
    "skill.install": ("새 스킬/플러그인을 설치합니다", "에이전트가 할 수 있는 일 자체"),
    # absorbed from the hook's card.py registry so consequence is the single
    # source of truth (decide() enforces explainability against THIS table).
    "agent.spawn": ("하위 에이전트를 시작합니다(각 호출은 개별로 게이트됨)", "새 에이전트가 할 수 있는 모든 행동"),
    "vcs.push": ("커밋을 원격 저장소에 푸시합니다", "원격 저장소(공개될 수 있음)"),
    "net.connect": ("egress 링 안에서 네트워크 연결을 엽니다", "허용된 호스트(읽기)"),
    "host.tool.": ("Zeus가 메타데이터를 모르는 호스트 도구를 실행합니다", "해당 도구가 다루는 시스템"),
}

_REVERSIBILITY_KO: Final[dict[Reversibility, str]] = {
    Reversibility.reversible: "예 — 언제든 되돌릴 수 있습니다",
    Reversibility.compensable: "부분적 — 복구 절차가 필요합니다",
    Reversibility.irreversible: "아니오 — 한 번 실행되면 되돌릴 수 없습니다",
}

_SIDE_EFFECT_KO: Final[dict[SideEffectClass, str]] = {
    SideEffectClass.none: "읽기만 하고 아무것도 바꾸지 않습니다",
    SideEffectClass.local_write: "내 컴퓨터 안에서만 바꿉니다",
    SideEffectClass.account_write: "내 계정/외부 서비스 상태를 바꿉니다",
    SideEffectClass.public_write: "공개적으로 보이는 것을 바꿉니다",
}


class ConsequenceCard(BaseModel):
    """The five answers, in plain Korean."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    what: str
    blast_radius: str
    reversible: str
    why: str
    precedent: str

    def lines(self) -> tuple[str, ...]:
        return (
            "무엇을: {0}".format(self.what),
            "어디에: {0}".format(self.blast_radius),
            "되돌리기: {0}".format(self.reversible),
            "왜: {0}".format(self.why),
            "전례: {0}".format(self.precedent),
        )


def explain(
    record: CapabilityRecord,
    *,
    args: Optional[dict[str, JsonValue]] = None,
    provenance: Optional[str] = None,
) -> Optional[ConsequenceCard]:
    """A vetted plain-language card, or None — and None means ESCALATE."""
    fragment = _family_fragment(record.capability_id)
    if fragment is None:
        return None
    what, where = fragment
    detail = _detail_of(args or {})
    precedent = (
        "이 능력은 지금까지 {0}회 성공적으로 실행되었습니다".format(record.trust.runs)
        if record.trust.measured and record.trust.runs > 0
        else "이 능력은 아직 검증된 실행 기록이 없습니다"
    )
    return ConsequenceCard(
        what=what + (detail and " ({0})".format(detail) or ""),
        blast_radius="{0} — {1}".format(where, _SIDE_EFFECT_KO[record.side_effect]),
        reversible=_REVERSIBILITY_KO[record.reversibility],
        why=provenance or "현재 목표 수행에 필요하다고 판단된 행동입니다",
        precedent=precedent,
    )


def render_plain_card(card: ConsequenceCard, *, reason: str) -> str:
    return "[Zeus 승인 요청] ({0})\n{1}".format(reason, "\n".join(card.lines()))


def _family_fragment(capability_id: str) -> Optional[tuple[str, str]]:
    if capability_id in _FAMILY_WHAT:
        return _FAMILY_WHAT[capability_id]
    for prefix, fragment in _FAMILY_WHAT.items():
        if prefix.endswith(".") and capability_id.startswith(prefix):
            return fragment
    return None


def _detail_of(args: dict[str, JsonValue]) -> str:
    for key in ("path", "command", "url", "recipient", "model"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            return text if len(text) <= 80 else text[:77] + "..."
    return ""
