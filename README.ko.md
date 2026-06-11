<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/zeus-symbol-transparent-white-tight.png">
    <source media="(prefers-color-scheme: light)" srcset="./assets/zeus-symbol-transparent-black-tight.png">
    <img src="./assets/zeus-symbol-transparent-black-tight.png" width="360" alt="Zeus: AI 에이전트 거버넌스 컨트롤 플레인" />
  </picture>
</p>

<p align="center">
  <a href="https://github.com/Orvek-dev/Zeus/releases"><img alt="Version" src="https://img.shields.io/badge/version-1.0.0--alpha.1-2ea44f"></a>
  <a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-0969da"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776ab">
  <img alt="Local first" src="https://img.shields.io/badge/local--first-control%20plane-6f42c1">
  <img alt="Tests" src="https://img.shields.io/badge/tests-1881%20passed-1f883d">
  <img alt="Conformance" src="https://img.shields.io/badge/conformance-88%20scenarios-8250df">
</p>

<p align="center">
  <a href="./README.md">English</a> ·
  <a href="#zeus">한국어</a> ·
  <a href="#왜-zeus를-만들었나">왜 Zeus를 만들었나</a> ·
  <a href="#quickstart-10분">Quickstart</a> ·
  <a href="#네-개의-관문">네 개의 관문</a> ·
  <a href="#문서">문서</a>
</p>

# Zeus

Zeus는 **AI 에이전트를 위한 로컬 우선(local-first) 거버넌스 컨트롤
플레인**입니다. 또 하나의 에이전트가 아닙니다. 실제 작업은 기존 에이전트
플랫폼 — Claude Code는 지금 라이브, hermes-agent와 OpenClaw는 어댑터 계약
동결·실호스트 검증 대기 — 이 그대로 수행하고, 그 플랫폼이 관문(게이트)을
통해 Zeus에 연결됩니다. Zeus는 무엇이 실행되어도 되는지 결정하고, 실제로
무슨 일이 있었는지 기록하고, 일어나서는 안 되는 일을 차단하며, 깨끗한
실적을 "덜 묻는 자율성"으로 바꿔 줍니다.

```text
호스트 에이전트 (Claude Code / hermes / OpenClaw)
   │ 훅              │ base_url            │ MCP                │ 네트워크/파일
   ▼                 ▼                     ▼                    ▼
 게이트 0 훅     게이트 1 LLM 프록시   게이트 2 MCP 게이트웨이  게이트 4 egress 링
   └────────────── decide() → auto | notify | ask | deny ──────────────┘
                   + 영수증 + 의무사항   (게이트 3: 원격 훅용 /zeus API)
   호스트가 자신의 도구를 직접 실행 → record(영수증, 결과)
   → 해시 체인 원장 · 신뢰 적립 · 거버넌스 커버리지 지표
```

전체 제품이 하나의 계약 위에 서 있습니다. `decide()`는 결정만 하고(훅
표면에서 Zeus는 호스트의 도구를 절대 대신 실행하지 않습니다), `record()`가
호스트의 실행 결과를 결정 영수증에 묶습니다.

**최종 행동-영수증 계약.** 호스트에 전달된 최종 행동과 원장의 최종 영수증은
언제나 같습니다. 최종 행동을 바꿀 수 있는 조건(egress 링 위반, 평어 설명
템플릿 부재)은 `decide()`의 **입력**이지, 응답의 사후 변조가 아닙니다. 이
불변식은 전용 컨포먼스 스위트가 모든 게이트에서 고정하고, 승인은 끝까지
TTL fail-closed이며, 소모된 "이번만" 그랜트는 어느 게이트의 어느 후속
프로세스에서도 되살아나지 않습니다.

그 계약 둘레에 커널 장기들이 있습니다.

- **최소권한 컴파일러** — 목표(objective)를 `AuthorityEnvelope`로 컴파일:
  티어가 매겨진 허용 능력(auto / ask-first / always-ask), 목표에서 유도되지
  않은 인접-위험 능력의 **명시적 잠금 목록**, 예산, 물어볼 가치가 있는
  질문(VoI). 목표 절로 추적되지 않는 능력은 봉투에 들어가지 못합니다 —
  "하는 김에"가 구조적으로 불가능합니다.
- **테인트 엔진** — 세션이 정보 흐름 라벨(untrusted / private)을 갖습니다.
  신뢰할 수 없는 데이터가 외부 싱크에 닿으면 강제 질문, 비밀 데이터가
  승인되지 않은 호스트로 향하면 즉시 거부, 에이전트가 자기 원장을 읽으면
  세션이 다시 오염됩니다(anti-Goodhart).
- **거버너** — 예산·호출 빈도·루프·신규성(novelty)·데드맨 한계를 사후
  경고가 아니라 **호출 전**에 강제합니다.
- **플라이트 리코더** — 거부를 포함한 모든 결정이 해시 체인 SQLite 원장에
  영수증을 남기고, 실행 결과가 `caused_by`로 연결되어 "왜 이런 일이
  일어났나"가 체인 추적 한 번이 됩니다.
- **단계별 승인** — 승인은 예/아니오가 아니라 이번만 · 이 세션 · 더 좁게 ·
  거절입니다. 상시 그랜트가 반복 질문을 잠재우고, 고위험 행동은 어떤
  그랜트로도 사전 허가되지 않으며, 그랜트 소모는 모든 게이트에서
  영속됩니다.
- **자격증명 브로커** — 에이전트는 비밀 참조로만 계획하고 원시 키를 절대
  쥐지 않습니다. 키는 허용된 결정일 때 송신 지점에서만 주입되고, 주입
  사실 자체가 실행 결과로 기록됩니다.

북극성 지표는 **주당 질문 횟수(asks/week)** 입니다. 영원히 잔소리하거나
모두 도장만 찍는 거버넌스가 아니라, 자율성을 벌어 내려가는 거버넌스입니다.

## 왜 Zeus를 만들었나

또 하나의 똑똑한 범용 AI 에이전트가 필요해서 만든 것이 아닙니다.

에이전트가 유능해질수록, 그들이 정말 옳은 일을 했는지 확인하는 일은 오히려
늘어납니다. 자신 있게 말하고, 도구를 돌리고, 계획을 만들며 계속 움직이지만
사용자는 여전히 물어야 합니다. 무엇을 했지? 왜 했지? 그럴 권한이 있었나?
원래 목표는 충족됐나? 결과를 증거로 되짚을 수 있나?

저는 그것이 진짜 문제라고 생각합니다 — 그리고 그것은 에이전트의 문제가
아니라 **컨트롤 플레인의 문제**입니다. 에이전트는 알아서 좋아집니다. 빠져
있는 것은 어떤 에이전트가 일하든 권한·예산·정보 흐름·증거를 일정하게
유지해 주는 층입니다. 호스트 플랫폼이 강해질수록 그 층은 더 중요해집니다.

Zeus는 그 층으로 만들어졌습니다. 무슨 일이 있었는지, 어떤 권한을 썼는지,
어떤 증거를 모았는지, 왜 일이 끝났다고 볼 수 있는지를 보여 줄 수 없다면,
끝난 척해서는 안 됩니다.

## 네 개의 관문

| 관문 | 하는 일 | 상태 |
| --- | --- | --- |
| **게이트 0 — Claude Code 훅** | PreToolUse → `decide()`, PostToolUse → `record()`. 정적 도구→능력 매핑, 셸 명령은 결정적 위험 분류, 다섯 답 + 단계별 응답의 승인 카드. | 라이브 (도그푸딩) |
| **게이트 1 — LLM 프록시 `/v1`** | OpenAI 호환. 인입: 호출 전 예산 → HTTP 429, 목표별 비용 귀속, 쿼터 기반 모델 전환(거버넌스 결정). 송출: 모델이 내는 모든 `tool_call`을 풀어 주기 전에 판정 — 스트림 조각은 통째로 버퍼링, 거부된 호출은 제거 후 차단 알림으로 대체. 비밀 위생 모드 `count / redact / block / ask` + 청크 경계를 넘는 스트리밍 마스킹. | 구현 완료, 합성 컨포먼스 |
| **게이트 2 — MCP 게이트웨이** | 다운스트림 도구는 격리 상태로 들어오고, 검토가 활성화하며, 스키마 바꿔치기(rug-pull)는 즉시 재격리, 설명·결과의 인젝션은 세션을 오염시키고, 도구별 예산이 붙습니다. | 구현 완료, 합성 컨포먼스 |
| **게이트 3 — zeusd Decision API** | 프록시 포트 위의 `POST /zeus/decide·record`, `GET /zeus/brief`. HMAC 페어링 — 무확인 연결은 절대 없음. hermes: 블로킹 `pre_tool_call` + 감쇠된 자식 주체(봉투 밖 서브에이전트 = DENY). OpenClaw: 내구성 있는 TTL fail-closed park의 exec 승인 릴레이. | 구현 완료, 고정 실호스트 검증 대기 (v2/v3 관문) |
| **게이트 4 — egress 링** | 호스트/경로 링을 정책보다 **먼저** 검사 — 링 위반은 무음 덮어쓰기가 아니라 DENY 영수증입니다. 키는 허용된 결정일 때 송신 지점에서만 주입. 링에서 [sandbox-runtime](https://github.com/anthropics/sandbox-runtime) 프로필을 방출합니다. | 링은 인프로세스 라이브; srt 래퍼를 통한 OS층 강제가 다음 마일스톤 |

## Quickstart (10분)

Python 3.10+ 기준, 새로 클론한 디렉터리에서:

```sh
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
```

**1. 로컬 컨트롤 플레인 초기화** (~/.zeus/control-plane: 원장·신뢰
카운트·그랜트·세션 테인트):

```sh
zeus init
```

**2. 첫 게이트 연결 — Claude Code 훅.** 프로젝트 디렉터리에서:

```sh
zeus connect claude-code --write   # .claude/settings.json에 PreToolUse/PostToolUse 훅 병합
```

**3. Claude Code에서 평소처럼 작업합니다.** 읽기는 조용히 통과하고, 첫 파일
수정이나 위험한 명령에서 다섯 가지 답 — 무엇을 / 어디까지(blast radius) /
되돌릴 수 있나 / 왜 / 전례 — 이 담긴 승인 카드가 뜹니다.

**4. 같은 질문에 두 번 답하지 마세요.** 신뢰하는 것은 면허를 내 주면 됩니다:

```sh
zeus approve fs.write --scope session --session-id <세션>   # 이 세션 동안
zeus approve fs.write --scope narrower --path /work/project # 이 경로만, 상시
```

**5. 에이전트가 실제로 무엇을 했는지 확인:**

```sh
zeus status                          # 결정 분포, 질문 수, 거버넌스 커버리지, 체인 무결성
zeus ledger --tail 20                # 최근 영수증
zeus ledger --why trust.ev.000042    # 한 행동 뒤의 인과 체인
```

**다른 호스트**는 프록시와 `/zeus` API로 연결합니다:

```sh
zeus proxy --upstream https://api.openai.com   # /v1 LLM 게이트 + /zeus Decision API (기본 루프백)
zeus pair --approve ZEUS-XXXX                  # 페어링은 절대 무확인이 아님
zeus policy --hygiene-mode redact --confirm    # 비밀 위생: count | redact | block | ask
```

Claude Code · hermes-agent · OpenClaw 연결 안내는
[CONNECTING.md](CONNECTING.md)에 있습니다. 훅 표면이 없는 호스트는 계약을
직접 호출합니다(`zeus decide` / `zeus record`). 기존 플랫폼 표면 전체는
`zeus dev` 아래에 있습니다 — [docs/commands.md](docs/commands.md) 참고.

## Zeus가 하는 일

| 층 | 의미 |
| --- | --- |
| Decision API v1 | 모든 게이트가 쓰는 단일 동결 계약. `decide()`가 auto/notify/ask/deny + 영수증 + 의무사항을 반환하고, `record()`가 호스트의 실행 결과를 그 영수증에 묶는다. |
| 영수증 정합성 | 호스트에 전달된 최종 행동 == 원장의 최종 영수증. 경계 위반과 설명가능성은 `decide()` 안에서 판정되며, 전용 컨포먼스가 이를 고정한다. |
| 권한 봉투 | 최소권한 컴파일러가 목표 프레임을 티어별 허용 능력, 명시적 잠금 목록, 예산, 물을 가치가 있는 질문으로 바꾸고 — 다음 제안은 실제 사용분으로 줄인다. |
| 결과 카드 | ask 결정은 다섯 가지 평어 답(무엇/어디에/되돌리기/왜/전례)으로 렌더링된다. 검증된 템플릿이 없는 부작용 능력은 조용한 자동 실행이 될 수 없고, 어떤 상시 면허도 그것을 덮지 못한다. |
| 테인트 흐름 | untrusted/private 라벨이 세션 단위로 지속되며 매 결정마다 치명적 3요소 규칙을 검사한다. |
| 거버너 | 호출 전 예산 하드스톱(run/objective/fleet), 능력별 속도 윈도, 루프 상한 + 무진전 감지, 처음 보는 호스트/수신자 에스컬레이션, 조용한 시간, 그리고 데드맨 스위치: 확인 없는 주간 다이제스트는 자율성을 강등시킨다. |
| 지갑 | 토큰 비용을 목표별 마이크로-USD로 계량, 주간 지출 다이제스트, 예산 초과 요청은 프로바이더 호출 전에 거절. |
| 비밀 위생 | 프록시가 응답에서 비밀 모양 텍스트를 탐지: count(기본) / redact(스트림 청크 경계를 넘어도 마스킹) / block(보류) / ask(검토 대기) — 모든 본문 변조는 자체 영수증을 남긴다. |
| 정책 팩 · NL 규칙 | `zeus policy --apply safe-assistant`, "weekly budget $12"류 규칙, 모드 변경 자체가 거버넌스 대상이며 확인·기록된다. |
| 플라이트 리코더 | 인과 간선이 달린 해시 체인 영수증, 통제된 원장 읽기(에이전트 뷰는 세션 한정·마스킹·감사·재오염), 커버리지 지표. |
| 신뢰 적립 | 실제 영수증이 능력별 신뢰를 만든다. 깨끗한 실적은 위험을 완화하고 범위를 줄이며, MCP 도구의 스키마가 바뀌면 즉시 재격리된다. |
| 인지 장기 (기본 OFF) | 장기 기억 쓰기는 redact된 후보로만 저장(오염된 후보는 hash+미리보기만 남고 영구 승격 불가); 스킬/플러그인 설치는 격리·해시 고정·인젝션 스캔 후에만 활성화. |
| 컨포먼스 | 게이트 0–4, 거버넌스 UX, 루프 거버넌스, 두 호스트 어댑터, 위생, 원격 안전, 영수증 정합성에 걸친 88개 동결 시나리오. 메이저 버전은 **고정된 실호스트**에서 95% 이상 + Zeus 밖 독립 계측 + 7일 무우회 소크로만 열린다. |

## Evidence

2026-06-11, 공개 소스 트리에서 측정. 이 수치는 결정적 로컬 회귀 증거이지,
프로덕션 준비의 증명이 아닙니다.

| 증거 표면 | 현재 결과 |
| --- | --- |
| 공개 단위·시나리오 스위트 | `1881`개 테스트 통과 |
| 컨포먼스 시나리오 | P3–P13 + 영수증 정합성에 걸쳐 `88`개 |
| 린트 | `ruff` 클린 |
| 패키지 메타데이터 | `zeus-agent==1.0.0a1` (알파 리셋; 메이저는 컨포먼스 게이트) |
| 원시 비밀 저장 증명 | 바이트 수준 스캔: 키가 담긴 기억 후보가 SQLite 파일에 마스킹 없이 닿지 않음 |

**정직한 경계.** 컨포먼스는 합성입니다 — 시뮬레이션된 호스트에 대해 계약을
동결한 것으로, 필요조건이지 충분조건이 아닙니다. `v2.0.0`은 **고정된
hermes-agent**가 95% 이상 + 7일 실트래픽 소크 + 무우회를 Zeus **밖의**
독립 계측으로 통과할 때에만, `v3.0.0`은 OpenClaw로 같은 절차를 반복할
때에만 출시됩니다. egress 링은 현재 인프로세스 판정 + 샌드박스 프로필
방출까지이며, Zeus가 OS층에서 직접 강제하지는 않습니다(그것이 다음
마일스톤이자 비협조적 호스트에 대한 유일한 실질 방어입니다). `/v1`은 기본
루프백 바인드이고, 비루프백은 발급 토큰(`zeus pair --issue-v1-token`,
TTL·취소 지원) 없이는 기동을 거부합니다. 인지 장기는 기본 OFF입니다.
호스팅 SaaS, 브라우저 자동화, 제3자 프로덕션 검증은 주장하지 않습니다.

## 문서

| 문서 | 목적 |
| --- | --- |
| [English README](README.md) | 영문 개요, 만든 이유, 퀵스타트, 문서 안내 |
| [호스트 연결 (한국어)](CONNECTING.ko.md) | Claude Code · hermes-agent · OpenClaw를 게이트에 연결하는 방법 ([English](CONNECTING.md)) |
| [한국어 문서 안내](docs/ko.md) | 한국어 읽기 순서와 문서 분류(현행/아카이브) |
| [Commands](docs/commands.md) | 레거시 CLI 카탈로그 (`zeus dev` 아래로 이동) |
| [Docker And OrbStack](docs/docker.md) | 로컬 Docker/OrbStack 빌드·실행·스모크 체크 |
| [Security policy](SECURITY.md) | 공개 보안 태세와 현재 알파 경계 |
| [Changelog](CHANGELOG.md) | 릴리스 역사 (재창립 이전 라인 포함) |

## License

Zeus는 MIT 라이선스로 배포됩니다. [LICENSE](LICENSE)를 참고하세요.
