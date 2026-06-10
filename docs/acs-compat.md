# ACS Manifest Read Compatibility

Zeus rides external agent-capability-spec (ACS-style) manifests instead of
fighting them. A host that already declares its tool surface and interception
points in an ACS manifest can plug into the Zeus Decision API without
re-describing anything: `acs_compat_runtime.load_acs_manifest` reads the
manifest and `capability_map` projects its interception points onto Zeus
capability ids.

```python
from zeus_agent.acs_compat_runtime import capability_map, load_acs_manifest

manifest = load_acs_manifest(manifest_text)   # JSON; YAML if PyYAML is present
mapping = capability_map(manifest)            # {"tool.pre_call": "fs.write", ...}
```

Scope and intent:

- **Read-only compatibility.** Zeus consumes the manifest; it does not emit,
  extend, or validate the upstream spec.
- **Field tolerance.** Both `interceptions` and `interception_points` are
  accepted, with `point`/`name`/`id` and `capability_id`/`capability`/
  `maps_to` as key variants — vendor manifests drift, the loader does not.
- **No YAML dependency.** The spec is YAML-first; Zeus parses JSON natively
  and uses PyYAML only when it happens to be installed. A compatibility shim
  is not a reason to grow the dependency tree.
- **Mapping is data, not inference.** Every interception point maps to an
  explicit Zeus `capability_id` that must exist in the capability registry to
  carry metadata (side effect, reversibility, trust). Unmapped or unregistered
  points fall back to the Decision API's conservative-unregistered path (ASK).
