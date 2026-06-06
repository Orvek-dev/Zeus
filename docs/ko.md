# Zeus 한국어 문서 안내

[English README](../README.md) · [한국어 README](../README.ko.md)

이 문서는 공개 문서의 한국어 읽기 순서를 제공합니다. 현재 모든 장문 설계 문서는
영어 canonical 문서를 기준으로 유지하고, 한국어 README와 이 안내 문서에서 핵심
맥락을 먼저 제공합니다.

## 먼저 읽기

1. [한국어 README](../README.ko.md)
   - Zeus를 왜 만들었는지
   - Zeus가 어떤 문제를 풀려고 하는지
   - Quickstart와 핵심 명령

2. [Commands](commands.md)
   - 설치 후 실제로 실행해볼 수 있는 public local CLI 명령

3. [Hermes comparison](hermes-comparison.md)
   - Hermes와 Zeus가 어떤 점에서 같고 다른지
   - Zeus가 왜 objective contract, authority, evidence 중심인지

4. [Live connection architecture](live-connection-architecture.md)
   - 외부 AI API, MCP, gateway, browser, terminal, sandbox를 어떻게 연결해야 하는지
   - 어떤 live surface가 아직 production-ready claim이 아닌지

5. [Security policy](../SECURITY.md)
   - local-first, no-secret-echo, authority/lease/evidence boundary

## 현재 문서 분류

| 문서 | 성격 |
| --- | --- |
| `README.md` | 영어 canonical 공개 진입점 |
| `README.ko.md` | 한국어 공개 진입점 |
| `docs/commands.md` | CLI 명령 카탈로그 |
| `docs/hermes-comparison.md` | 현재 Zeus와 Hermes 비교 |
| `docs/live-connection-architecture.md` | live 연결 목표 아키텍처 |
| `docs/hermes-grade-platform-master-design.md` | 장기 목표 설계 |
| `docs/hermes-live-platform-absorption-master-plan.md` | Hermes live platform 흡수 장기 계획 |
| `docs/zeus-*-boundary.md` | 과거 RC 및 공개/보안 경계 기록 |

## 한국어 번역 정책

- README와 주요 독자 안내는 한국어로 제공합니다.
- 장문 설계 문서는 영어 canonical을 유지하되, 한국어 README/문서 안내에서
  읽는 순서와 핵심 의미를 제공합니다.
- 문서가 제품의 실제 구현 상태와 다를 경우, 현재 구현 상태와 release boundary를
  우선합니다.
