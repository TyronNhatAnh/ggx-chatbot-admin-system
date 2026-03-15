# Feature Exploration Guide

This guide explains the standard workflow for generating feature docs in this repository.

## Output Contract

Each feature generates artifacts under docs/features/<feature_name>/:

- index.json: structured feature index (use cases, endpoints, schemas, business rules, evidence)
- requirement.md: human-readable requirement document
- index_error.json: compact troubleshooting payload when strict validation fails (truncated preview)
- requirement_error.md: compact markdown preview when strict validation fails (truncated preview)

Notes:

- Error artifacts are overwritten on each failed run (no per-run accumulation).
- When a run succeeds, stale error artifacts are automatically removed.

## Strict Evidence Policy (Always On)

Feature generation is strict evidence only:

1. no inferred or assumed statements
2. every use case and endpoint must include evidence refs
3. evidence refs must point to matched source files
4. if evidence is missing, output must state UNKNOWN/evidence_gap
5. invalid output is rejected and stored only in error artifacts

## Standard Workflow

Fast path (recommended):

```bash
. .venv/bin/activate
python scripts/explore_feature.py --interactive
```

or one-line auto mode:

```bash
. .venv/bin/activate
python scripts/explore_feature.py --feature "check price for guest and home moving"
```

Manual path:

1. Create a feature spec from template:
   - copy explorer/feature_specs/_template.yaml
   - rename to explorer/feature_specs/<feature_name>.yaml
2. Fill feature scope:
   - be_files and fe_files globs
   - api_scope
   - go_types and ts_types
   - business_terms
3. Run generation:

```bash
. .venv/bin/activate
python scripts/explore_feature.py --spec explorer/feature_specs/<feature_name>.yaml
```

Spec-only mode (no Gemini call yet):

```bash
python scripts/explore_feature.py --feature "your feature" --write-spec-only
```

4. Review output:
   - check docs/features/<feature_name>/index.json for evidence_refs and logic_evidence
   - check docs/features/<feature_name>/requirement.md for detailed use cases

## Run Discovery Or Not?

- Use scripts/run_discovery.py when you need broad FE/BE inventory or mappings are stale.
- Use scripts/explore_feature.py when feature scope is already known and you need deep requirement/spec output.

## Fast Checklist

- spec globs narrow enough to include only feature-relevant files
- all APIs in api_scope are real and currently used
- output has no inference words (inferred, assumed, likely, probably)
- every use case maps to at least one endpoint and evidence ref
