# Zeus 한국어 문서 안내

[English README](../README.md) · [한국어 README](../README.ko.md)

이 문서는 공개 문서의 한국어 읽기 순서를 제공합니다. 영어 문서가
canonical이며, 핵심 진입 문서(README, CONNECTING)는 한국어 번역을
함께 유지합니다.

## 먼저 읽기

1. [한국어 README](../README.ko.md)
   - Zeus를 왜 만들었는지, 네 개의 관문, 최종 행동-영수증 계약
   - Quickstart와 정직한 알파 경계
2. [호스트 연결 (한국어)](../CONNECTING.ko.md)
   - Claude Code · hermes-agent · OpenClaw를 게이트에 연결하는 방법
   - 페어링(무확인 연결 금지), 예산, 정책, 다이제스트
3. [Security policy](../SECURITY.md) (영어)
   - 로컬 우선 기본값, 영수증 정합성, 현재 알파 경계
4. [Docker And OrbStack](docker.md) (영어)
   - 로컬 컨테이너 빌드·실행·스모크 체크
5. [Legacy Wave Attic](../attic/legacy-wave/README.md) (영어)
   - 재창립 이전 wave 하네스의 보관 위치와 제외 규칙

## 현재 문서 분류

| 문서 | 성격 |
| --- | --- |
| `README.md` / `README.ko.md` | 공개 진입점 (EN canonical / KO 번역) |
| `CONNECTING.md` / `CONNECTING.ko.md` | 호스트 연결 가이드 (EN canonical / KO 번역) |
| `SECURITY.md` | 보안 태세와 알파 경계 |
| `CHANGELOG.md` | 릴리스 역사 (재창립 이전 라인 포함) |
| `docs/docker.md` | 컨테이너 사용법 |
| `docs/acs-compat.md` | ACS 매니페스트 읽기 호환 |
| `docs/private-dogfood-eval-boundary.md` | private live-host dogfood/eval 자산 분리 규칙 |
| `attic/legacy-wave/` | **아카이브** — 재창립 이전 wave CLI/eval/test 하네스. 기본 테스트·제품 CLI·릴리스 증거에서 제외 |
| `docs/hermes-*.md`, `docs/live-connection-architecture.md`, `docs/zeus-*-boundary.md`, `docs/zeus-w205-w212-hard-close.md` | **아카이브** — 재창립 이전(v0.x–v6.x) 기록. 파킹된 하네스가 참조하므로 원문 보존. 내용이 README와 다르면 README가 우선 |

## 한국어 번역 정책

- README와 CONNECTING(호스트 연결)은 한국어 번역을 유지합니다.
- 운영 문서(commands/docker/acs-compat)와 보안 정책은 영어 canonical을
  유지하되, 이 안내에서 읽는 순서를 제공합니다.
- 문서가 제품의 실제 구현 상태와 다를 경우, 현재 구현 상태와 README의
  정직한 경계 서술이 우선합니다.
