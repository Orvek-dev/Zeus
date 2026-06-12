# Private Dogfood Eval Boundary

Zeus dogfooding uses two artifact classes:

- public product code and public regression tests that can ship with the repo
- private live-host dogfood/eval assets used to drive Hermes/OpenClaw/Codex QA

Keep them separated. The private dogfood/eval assets are operator evidence, not
product source.

## Private By Default

These paths must stay local and uncommitted:

- `evals/`
- `tests/test_live_host_eval_tree.py`

`evals/` contains live-host pins, prompts, result schemas, reports, and harness
files for local soak/dogfood operation. It may reference local host versions,
operator workflows, screenshots, API setup assumptions, and non-public QA
criteria.

`tests/test_live_host_eval_tree.py` validates that private eval tree shape. It
is useful locally, but it depends on private assets and must not be part of the
public test suite.

## Public Counterparts

When a private dogfood finding becomes product behavior, move only the product
contract into public code:

- implementation under `src/zeus_agent/`
- public tests under `tests/` or `tests/conformance/`
- release-facing notes in `CHANGELOG.md`
- public user docs under `README.md`, `CONNECTING.md`, or `docs/`

Do not copy private prompts, reports, raw dogfood logs, local host setup
details, secrets, or operator-only traces into public docs.

## Commit Rule

Before staging a release or dogfood fix, run:

```bash
git status --short --ignored
```

Expected state:

- `evals/` is ignored
- `tests/test_live_host_eval_tree.py` is ignored
- public code and public docs are the only candidates for staging

If a future task needs a public live-host eval specification, create a sanitized
fixture under a different public path and make sure it contains no local
operator evidence.
