# Discovery Output

This directory contains generated artifacts from scripts/run_discovery.py.

## Artifacts

| File | Produced by | Contents |
|------|-------------|----------|
| web2/fe_api_inventory.json | scan-fe | Outgoing HTTP calls found in the Web2 frontend repo |
| order-services/be_endpoints.json | scan-be | Backend endpoint definitions for order-services |
| flow_mappings.json | map-flows | FE call to BE endpoint mappings |
| order-services/code_context/*.context.md | scan-be | Handler-level backend code context snippets |

Legacy flat paths are still read as fallback for backward compatibility.

## When To Run Discovery

Run discovery when you need broad system inventory and FE/BE mapping, for example:

1. first-time onboarding to new FE/BE repos
2. major API changes made previous mappings stale
3. preparing candidate feature scopes

For deep analysis of one known feature, use scripts/explore_feature.py instead.

## Regenerate

```bash
. .venv/bin/activate
python scripts/run_discovery.py scan-all
```

These files are generated artifacts. Do not edit them manually.
