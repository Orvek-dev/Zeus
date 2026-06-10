<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/zeus-symbol-transparent-white-tight.png">
    <source media="(prefers-color-scheme: light)" srcset="./assets/zeus-symbol-transparent-black-tight.png">
    <img src="./assets/zeus-symbol-transparent-black-tight.png" width="360" alt="Zeus: goal-oriented AI agent" />
  </picture>
</p>

<p align="center">
  <a href="./README.md">English</a> ·
  <a href="#zeus-agent">한국어</a> ·
  <a href="#왜-zeus를-만들었나">왜 Zeus를 만들었나</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#문서">문서</a>
</p>

# Zeus Agent

Zeus는 목적 지향형 AI 에이전트 런타임입니다. Zeus의 중심은 단순히
에이전트가 더 많이 행동하게 만드는 것이 아닙니다. 사용자의 목적을
정확하게 이해하고, 통제된 권한 안에서 움직이며, 자신이 한 일을
기록하고, 완료 판단을 증거로 설명할 수 있게 만드는 것입니다.

```text
Hermes식 범용성 = provider + tool + session + gateway + MCP + skill
Zeus의 중심    = objective contract + authority gate + evidence + promotion review
```

Zeus는 Hermes의 넓은 플랫폼 형태에서 배울 것은 흡수하되, 중심축은 다르게
잡습니다. 공개 `v6.1.0` 릴리스는 local-first governed platform boundary입니다.
Goal Intelligence, Cognitive Provider Activation, Objective Compiler Workflow UX,
Dynamic Workflow DAG planning, Productized Platform status,
ObjectiveRun start/status/export, Governed Live Slice authority UX,
Governed Live Connector Platform, Higher-Order Agent OS status,
Live Platform Beta status,
provider/MCP/tool/gateway/runtime 계약,
memory/ontology surface, self-evolution review queue, release-gated evidence check를 제공합니다.

`v6.1.0`에서는 Trust Loop refoundation spine이 추가됐습니다. action
reversibility, AUTO/NOTIFY/ASK/DENY 권한 판단, approval envelope, undo proof,
hash-chained evidence ledger, decision receipt, approval queue, plan tournament,
progressive trust proposal, skill manifest enforcement가 들어갔습니다. dogfood용
OpenAI chat 경로도 이제 네트워크 실행 전에 Trust Loop를 통과합니다. 다만 더
넓은 MCP, gateway, browser, plugin, remote sandbox production execution은 각
surface가 같은 spine으로 retrofit되기 전까지 계속 gated 상태입니다.

## 왜 Zeus를 만들었나

나는 또 하나의 똑똑한 범용 AI 에이전트를 만들고 싶어서 Zeus를 만든 것이
아닙니다.

AI 에이전트가 발전할수록, 에이전트가 실제로 일을 제대로 하고 있는지
확인하고 검수하는 부담도 같이 커졌습니다. 에이전트는 그럴듯하게 말하고,
도구를 실행하고, 계획을 만들고, 계속 움직일 수 있습니다. 하지만 사용자는
여전히 물어야 합니다. 무엇을 했는가? 왜 그렇게 했는가? 그 작업을 할
권한이 있었는가? 처음의 목적을 실제로 만족했는가? 그 결과를 증거로
추적할 수 있는가?

나는 이 지점이 문제라고 생각했습니다.

내가 생각하는 이상적인 에이전트는 단순히 범용적이고, 자기개선이 가능하고,
똑똑한 에이전트가 아닙니다. 사용자의 목적을 정확하게 이해하고, 통제된
권한과 안전한 규칙 안에서 움직이며, 자신이 한 일을 기록하고, 왜 그런
결정을 했는지 드러내고, 결과를 증거로 증명할 수 있어야 합니다.

Zeus는 이 생각에서 시작됐습니다.

목표는 단순히 계속 행동하는 에이전트를 만드는 것이 아닙니다. 사용자의
목적을 끝까지 밀고 나가되, 그 과정이 추적 가능하고, 통제 가능하고,
검수 가능해야 합니다. 에이전트가 무엇을 했는지, 어떤 권한을 사용했는지,
어떤 증거를 남겼는지, 왜 완료라고 판단했는지 보여줄 수 없다면, Zeus는
그 일을 완료했다고 말해서는 안 됩니다.

## Quickstart

Python 3.10 이상에서 실행합니다.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m pytest -q
```

처음 확인할 만한 로컬 표면은 아래 정도면 충분합니다.

```sh
zeus kernel-status
zeus productized-platform --scenario status --json
zeus cognitive-provider-activation --scenario fake-provider-intent --objective "제우스야, 내 목적을 governed workflow로 정리해줘." --json
zeus goal-intelligence-runtime --scenario understand-objective --objective "병렬 작업자를 쓰는 리서치 기반 코딩 워크플로우를 만들어줘." --task-count 6 --requires-code --requires-research --json
zeus objective-start --objective "제우스야, 내 목적을 evidence-backed run으로 정리해줘." --acceptance-criterion objective-run-created --json
zeus objective-compile-workflow --objective "제우스야, 이 목적을 governed workflow로 컴파일해줘." --requires-code --task-count 4 --json
zeus governed-live-connectors --scenario trusted-local-smoke --json
zeus higher-order-agent-os --scenario operator-cockpit --json
zeus governed-live-slice --surface provider --capability-id provider.local-smoke --scenario local-smoke --json
zeus live-platform-beta --scenario status --json
zeus release-gated-ulw --target-version v6.1.0 --json
```

더 긴 명령 목록은 [docs/commands.md](docs/commands.md)를 보세요.

## Zeus가 하는 일

Zeus는 열린 요청을 검수 가능한 실행으로 바꿉니다.

| 계층 | 의미 |
| --- | --- |
| Objective contract | 사용자의 목적을 acceptance criteria, assumption, unknown, evidence obligation으로 정리합니다. |
| Objective run | 시작된 목적을 local run으로 저장하고 start/status/export와 evidence 기반 완료 판정을 제공합니다. |
| Objective Compiler Workflow | 목적을 intent frame, 필요한 인터뷰 질문, workflow DAG, authority requirement, evidence plan으로 컴파일합니다. |
| Governed Live Connector Platform | provider, MCP, gateway, local sandbox connector smoke를 같은 objective, lease, approval, broker evidence, credential, sandbox, audit 요구사항으로 검수합니다. |
| Higher-Order Agent OS | persona, Objective Compiler, governed connector, TUI cockpit contract, recursive improvement review, plugin skeleton, remote sandbox contract, tenant/auth contract, public production boundary를 하나의 제품 표면으로 보고합니다. |
| Governed live slice | live-capable 작업 전 objective, lease, approval, broker evidence, credential, sandbox, audit 요구사항 누락을 설명하고 차단합니다. |
| Live platform beta | persona, setup/status cockpit, ObjectiveRun, authority UX, CLI, Python library, public production-live boundary를 beta 상태로 집계합니다. |
| Authority gate | capability, path, credential, tool, live surface가 허용된 경우에만 실행됩니다. |
| Runtime lease | live-capable 작업은 임시 권한, 승인, sandbox, credential, audit 요구사항에 묶입니다. |
| Evidence record | 완료 판단은 말투가 아니라 artifact, receipt, test, trace, reviewable output에 기반합니다. |
| Promotion review | memory, ontology, workflow pattern, skill, rule은 검토 전까지 candidate-only 상태로 남습니다. |
| Public boundary | 무엇이 준비됐고, 무엇이 차단됐고, 무엇이 dry-run/future인지 과장 없이 보고합니다. |

## Zeus Core Language

Zeus의 제품 언어는 12개 핵심 축으로 제한합니다. 기술 runtime 이름은
그대로 유지되고, 제품 이름이 runtime module을 대체하지 않습니다.

| Product name | Technical anchor |
| --- | --- |
| Zeus Kernel | `objective_runtime`, `verification_runtime`, evidence/authority center |
| Athena | `objective_runtime` |
| Thunderbolt | `runtime_lease` |
| Aegis | `security_runtime`, lease, sandbox policy |
| Mercury | `transport_runtime`, `connector_runtime`, MCP/API/gateway routing |
| Apollo | `model_runtime`, `provider_runtime`, eval boundaries |
| Hephaestus | `tool_runtime` |
| Poseidon | `gateway_runtime` |
| Artemis | `research_runtime` |
| Demeter | `ontology_runtime`, durable state |
| Olympus | `orchestration_runtime`, work-loop coordination |
| Prometheus | `skill_evolution` |

Hermes는 upstream/reference입니다. Mercury는 Zeus 내부 transport 제품명입니다.

## Evidence

최신 공개 안전 검증 스냅샷은 2026-06-09 기준입니다. 이 숫자는 public source
release의 deterministic local regression evidence이며, production readiness를
증명하는 것은 아닙니다.

| Evidence surface | Current result |
| --- | --- |
| Public unit and scenario suite | `1516` public tests passed |
| Final architecture eval | `10/10` checks passed |
| Total architecture eval | `9/9` checks passed |
| Package build | `zeus-agent==6.1.0` sdist/wheel build passed |

이 릴리스는 hosted SaaS readiness, production external provider execution,
production MCP catalog, unattended gateway operation, browser/terminal
automation, remote sandbox hard isolation, third-party production validation을
claim하지 않습니다.

## 문서

| 문서 | 목적 |
| --- | --- |
| [English README](README.md) | 영어 canonical README |
| [한국어 문서 안내](docs/ko.md) | 공개 문서의 한국어 안내와 읽는 순서 |
| [Commands](docs/commands.md) | public local surface용 CLI 명령 카탈로그 |
| [Docker And OrbStack](docs/docker.md) | 로컬 Docker/OrbStack 빌드, 실행, smoke check, volume 안내 |
| [Hermes comparison](docs/hermes-comparison.md) | Hermes와 Zeus의 아키텍처 차이 |
| [Live connection architecture](docs/live-connection-architecture.md) | real AI API, MCP, tool, gateway, browser, terminal, sandbox 연결 설계 |
| [Security policy](SECURITY.md) | 공개 보안 posture와 governed live boundary |
| [Changelog](CHANGELOG.md) | 릴리스 히스토리 |

## License

Zeus는 MIT License로 공개됩니다. [LICENSE](LICENSE)를 확인하세요.
