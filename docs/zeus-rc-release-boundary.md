# Zeus RC Release Boundary

This document is the W211 release-candidate boundary for package and release
handling in the current local checkout.

## Local Candidate

The current version source is `pyproject.toml`. Existing local package
artifacts under `dist/` can be inspected as package candidates, but they do not
prove that the current working tree is release-ready.

## Blocked Publication Actions

From this non-git working directory, Zeus must not:

- create or move a tag
- push a branch
- publish a GitHub release
- claim project-mode release readiness
- claim production-live readiness

## Required Future Release Path

Real public release publication must happen from a git-backed project checkout
after these checks pass:

1. version source of truth is updated
2. changelog/release notes match the version
3. tests, evidence gates, security review, and release gate pass
4. rollback path is documented
5. private harness, evidence, plans, specs, and local runtime state are excluded
6. tag and GitHub release are created only after the candidate gate passes

The W211 RC claim is local package boundary readiness only, not publication.
