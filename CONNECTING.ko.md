# 호스트 에이전트를 Zeus에 연결하기

[English](CONNECTING.md) · [한국어 문서 안내](docs/ko.md)

Zeus는 로컬 우선 거버넌스 컨트롤 플레인입니다. 에이전트는 하던 일을 그대로
하고, Zeus가 네 개의 관문(LLM 프록시 · MCP 게이트웨이 · 결정 훅 · egress
링)에서 결정·기록·승인·차단합니다. 모델 키는 호스트 쪽에 남습니다.

```
zeus init                 # ~/.zeus/control-plane 생성
zeus proxy --upstream https://api.openai.com   # zeusd: /v1 프록시 + /zeus API
```

페어링은 **절대 무확인이 아닙니다**: 에이전트가 연결을 요청하면 코드를
보여 주고, 사람이 직접 승인합니다 — 정책 서버가 몰래 바꿔치기되면 전체가
무너지기 때문입니다.

```
zeus pair --approve ZEUS-XXXX
```

## Claude Code (게이트 0 — PreToolUse/PostToolUse 훅)

```
zeus connect claude-code --write --project-dir .
```

이제 모든 도구 호출이 `decide()`를 거치고, 결과는 `record()`로 돌아옵니다.
`zeus status`(커버리지, 질문 수, 체인)와 `zeus ledger --tail 20`으로
확인하세요.

## hermes-agent (블로킹 pre_tool_call 훅 + 프록시 + 게이트웨이)

```
zeus connect hermes      # config.yaml 패치와 페어링 절차 출력
```

- `model.base_url` → `http://127.0.0.1:8788/v1` (비용 계량, 예산 429,
  tool_call 인터셉트)
- `pre_tool_call` 훅 → `POST /zeus/decide` (페어링 서명, 블로킹)
- `mcp_servers` → `zeus gateway` (격리, rug-pull 방어)
- 서브에이전트는 감쇠된 자식 주체입니다: 봉투 밖 요청은 **거부**됩니다.
- 세션 복구: `GET /zeus/brief?session_id=...`가 영수증 타임라인을
  반환합니다 — 범위 한정, 마스킹, 기록되며 untrusted로 태깅됩니다.

## OpenClaw (프록시 우선 + exec 승인 릴레이)

```
zeus connect openclaw    # 프로바이더/MCP 패치와 릴레이 계약 출력
```

- `baseUrl` → 프록시(`/v1`): exec 외 도구는 사전 훅이 없으므로 tool_call을
  응답 스트림에서 인터셉트합니다.
- exec → Zeus가 operator 클라이언트로 `exec.approval.requested`를 구독하고
  영수증과 함께 resolve합니다. 위험한 명령은 사람이 답할 때까지 대기합니다.
- ClawHub 셀프 온보딩: `zeus-connect` 스킬이 위 단계를 안내합니다 —
  페어링 승인은 여전히 사람 몫입니다.

## 예산, 정책, 리듬

```
zeus budget --scope objective --id obj.email --limit 2000000   # 마이크로-USD
zeus policy --apply safe-assistant --confirm
zeus policy --rule "weekly budget $12" --confirm
zeus policy --hygiene-mode redact --confirm    # 비밀 위생: count | redact | block | ask
zeus digest            # 주간 요약; `--ack`가 데드맨 스위치를 리셋
```

확인하지 않은 다이제스트는 자율성을 강등시킵니다(부작용 호출이 당신이
돌아올 때까지 ask로 바뀜). 처음 보는 호스트/수신자는 한 번 에스컬레이션된
뒤 학습됩니다.
