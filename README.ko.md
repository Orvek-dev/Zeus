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
</p>

<p align="center">
  <a href="./README.md">English</a> ·
  <a href="#zeus">한국어</a> ·
  <a href="#왜-zeus를-만들었나">왜 Zeus를 만들었나</a> ·
  <a href="#quickstart-10분">Quickstart</a> ·
  <a href="#문서">문서</a>
</p>

# Zeus

Zeus는 **AI 에이전트를 위한 로컬 우선(local-first) 거버넌스 컨트롤
플레인**입니다. 또 하나의 에이전트가 아닙니다. 실제 작업은 기존 에이전트
플랫폼 — 지금은 Claude Code, 앞으로 hermes-agent와 OpenClaw — 이 그대로
수행하고, 그 플랫폼이 게이트를 통해 Zeus에 연결됩니다. Zeus는 무엇이
실행되어도 되는지 결정하고, 실제로 무슨 일이 있었는지 기록하며, 깨끗한
실적을 "덜 묻는 자율성"으로 바꿔 줍니다.

```text
호스트 에이전트 (Claude Code / hermes / OpenClaw)
      │  모든 도구 호출, 실행 직전
      ▼
Zeus decide(주체, 능력, 인자, 컨텍스트)
      → auto | notify | ask | deny  + 영수증 + 의무사항
      ▼
호스트가 자신의 도구를 직접 실행 → record(영수증, 결과)
      → 해시 체인 원장 · 신뢰 적립 · 거버넌스 커버리지
```

전체 제품이 하나의 계약 위에 서 있습니다. `decide()`는 결정만 하고(훅
표면에서 Zeus는 호스트의 도구를 절대 대신 실행하지 않습니다), `record()`가
호스트의 실행 결과를 결정 영수증에 묶습니다. 그 계약 둘레에 커널 장기들이
있습니다.

- **최소권한 컴파일러** — 목표(objective)를 `AuthorityEnvelope`로 컴파일:
  티어가 매겨진 허용 능력(auto / ask-first / always-ask), 목표에서 유도되지
  않은 인접-위험 능력의 **명시적 잠금 목록**, 예산, 물어볼 가치가 있는
  질문(VoI). 목표 절로 추적되지 않는 능력은 봉투에 들어가지 못합니다 —
  "하는 김에"가 구조적으로 불가능합니다.
- **테인트 엔진** — 세션이 정보 흐름 라벨(untrusted / private)을 갖습니다.
  신뢰할 수 없는 데이터가 외부 싱크에 닿으면 강제 질문, 비밀 데이터가
  승인되지 않은 호스트로 향하면 즉시 거부, 에이전트가 자기 원장을 읽으면
  세션이 다시 오염됩니다(anti-Goodhart).
- **거버너** — 예산·호출 빈도·루프 한계를 사후 경고가 아니라 **호출 전**에
  강제합니다.
- **플라이트 리코더** — 거부를 포함한 모든 결정이 해시 체인 SQLite 원장에
  영수증을 남기고, 실행 결과가 `caused_by`로 연결되어 "왜 이런 일이
  일어났나"가 체인 추적 한 번이 됩니다.
- **단계별 승인** — 승인은 예/아니오가 아니라 이번만 · 이 세션 · 더 좁게 ·
  거절입니다. 상시 그랜트가 반복 질문을 잠재우고, 고위험 행동은 어떤
  그랜트로도 사전 허가되지 않습니다.
- **자격증명 브로커** — 에이전트는 `secret-proof://` 참조로만 계획하고 원시
  키를 절대 쥐지 않습니다. 봉인된 비밀은 허용된 결정 + 승인된 호스트일 때
  송신 지점에서만 풀립니다.

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

훅 표면이 없는 호스트는 계약을 직접 호출합니다. `zeus decide`가
`DecisionRequest` JSON을 읽어 결정+영수증을 출력하고, `zeus record`가 결과를
묶습니다. 기존 플랫폼 표면 전체(그리고 컨포먼스 하니스로 강등된
objective-run 실행기)는 `zeus dev` 아래에 있습니다 —
[docs/commands.md](docs/commands.md)의 각 명령 앞에 `dev`를 붙이면 됩니다.

## Zeus가 하는 일

| 층 | 의미 |
| --- | --- |
| Decision API v1 | 모든 게이트가 쓰는 단일 동결 계약. `decide()`가 auto/notify/ask/deny + 영수증 + 의무사항을 반환하고, `record()`가 호스트의 실행 결과를 그 영수증에 묶는다. |
| 권한 봉투 | 최소권한 컴파일러가 목표 프레임을 티어별 허용 능력, 명시적 잠금 목록, 예산, 물을 가치가 있는 질문으로 바꾸고 — 다음 제안은 실제 사용분으로 줄인다. |
| 게이트 0: Claude Code 훅 | PreToolUse → decide, PostToolUse → record. 정적 도구→능력 매핑, 셸 명령은 결정적 위험 분류 후 판정. |
| 승인 카드 | ask 결정은 다섯 답(무엇/어디에/되돌리기/왜/전례)과 단계별 응답(이번만/이 세션/더 좁게/거절)으로 렌더링된다. 평어 설명 템플릿이 없으면 자동 실행도 없다. |
| 테인트 흐름 | untrusted/private 라벨이 세션 단위로 지속되며 매 결정마다 치명적 3요소 규칙을 검사한다. |
| 거버너 | 호출 전 예산 하드스톱(run/objective/fleet), 능력별 속도 윈도, 루프 반복 상한 + 무진전 감지. |
| 플라이트 리코더 | 인과 간선이 달린 해시 체인 영수증, 통제된 원장 읽기(에이전트 뷰는 세션 한정·마스킹·감사·재오염), 커버리지 지표. |
| 신뢰 적립 | 실제 영수증이 능력별 신뢰를 만든다. 깨끗한 실적은 위험을 완화하고 범위를 줄이며, MCP 도구의 스키마가 바뀌면 즉시 재격리된다. |
| 컨포먼스 | 호스트별 고정 시나리오 스위트(스타터 12 → 약 40)가 메이저 버전의 유일한 관문: 95% 이상 + 7일 무우회 소크. |
| 공개 경계 | Zeus는 무엇이 거버넌스 아래 있고, 무엇이 우회됐고, 무엇이 designed/prepared/dry-run/future인지 그대로 보고한다. |

## Zeus Core Language

Zeus 코어 언어는 정확히 12개의 제품 도메인 기둥으로 구성됩니다. 기술 런타임
식별자는 보존되며, 제품 도메인 라벨이 런타임 모듈 이름을 바꾸지 않습니다.

| Product name | Technical anchor |
| --- | --- |
| Zeus Kernel | `objective_runtime`, `verification_runtime`, evidence/authority 센터 |
| Athena | `objective_runtime` |
| Thunderbolt | `runtime_lease` |
| Aegis | `security_runtime`, lease, sandbox 정책 |
| Mercury | `transport_runtime`, `connector_runtime`, MCP/API/gateway 라우팅 |
| Apollo | `model_runtime`, `provider_runtime`, eval 경계 |
| Hephaestus | `tool_runtime` |
| Poseidon | `gateway_runtime` |
| Artemis | `research_runtime` |
| Demeter | `ontology_runtime`, 영속 상태 |
| Olympus | `orchestration_runtime`, work-loop 조정 |
| Prometheus | `skill_evolution` |

Hermes는 업스트림/참조 전용입니다. Mercury는 Zeus 내부 전송 제품명입니다.

## Evidence

최신 공개 안전 로컬 증거 스냅샷은 2026-06-11에 측정되었습니다. 이 수치는
공개 소스 릴리스의 결정적 로컬 회귀 증거이지, 광범위한 프로덕션 준비의
증명이 아닙니다.

| 증거 표면 | 현재 결과 |
| --- | --- |
| 공개 단위·시나리오 스위트 | `1791`개 공개 테스트 통과 |
| 컨포먼스 스타터 스위트 | `12/12` 거버넌스 시나리오 통과 |
| 패키지 메타데이터 | `zeus-agent==1.0.0a1` (알파 리셋; 메이저는 컨포먼스 게이트) |

알파는 호스팅 SaaS 준비, 프로덕션 외부 프로바이더 실행, 프로덕션 MCP
카탈로그, 무인 게이트웨이 운영, 브라우저·터미널 자동화, 원격 샌드박스 강한
격리, 제3자 프로덕션 검증을 주장하지 않습니다. `v2.0.0`은 하나의 실제
호스트 통합이 고정된 컨포먼스 스위트를 95% 이상 + 7일 실트래픽 무우회
소크로 통과할 때에만 출시됩니다.

## 문서

| 문서 | 목적 |
| --- | --- |
| [English README](README.md) | 영문 개요, 만든 이유, 퀵스타트, 문서 안내 |
| [Commands](docs/commands.md) | 레거시 CLI 카탈로그 (`zeus dev` 아래로 이동) |
| [Docker And OrbStack](docs/docker.md) | 로컬 Docker/OrbStack 빌드·실행·스모크 체크 |
| [Hermes comparison](docs/hermes-comparison.md) | Hermes 기준 아키텍처와 Zeus의 거버넌스 커널/런타임 분리 이유 |
| [Security policy](SECURITY.md) | 공개 보안 태세와 현재 거버넌스 라이브 경계 |
| [Changelog](CHANGELOG.md) | 릴리스 역사 (재창립 이전 라인 포함) |

## License

Zeus는 MIT 라이선스로 배포됩니다. [LICENSE](LICENSE)를 참고하세요.
