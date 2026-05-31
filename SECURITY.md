# Security Policy

Zeus is local-first and local-only by default.

## Defaults

- No remote telemetry.
- No cloud sync by default.
- No execution without blueprint approval.
- No raw secrets in logs, ontology, memory, or artifacts.
- Local private state is written under `~/.zeus` with restrictive permissions.

## Reporting

Please report security issues privately before public disclosure.

## Current Alpha Boundary

This repository currently implements blueprint, approval, local process sandbox,
Mneme evidence, Sisyphus progress reporting, skill lifecycle, and registry
scaffolds.

- The sandbox executor is a local process sandbox. It gates approval, paths,
  environment, obvious network/destructive commands, and timeout budgets, but it
  is not hard isolation.
- External network access is deny-by-default in the first runtime.
- Provider authentication stores environment variable names only, never key
  values.
- GitHub publishing prep never commits, pushes, or creates repositories.
