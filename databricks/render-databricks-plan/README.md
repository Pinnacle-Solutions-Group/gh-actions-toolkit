# render-databricks-plan

A composite GitHub Action that turns `databricks bundle plan -o json`
output into a Markdown summary posted to the GitHub Actions job summary.
It's the audit trail an operator reads without downloading an artifact —
so a bug here means a silently wrong or missing audit record.

## Usage

Reference the action from a consumer workflow by its full path in this
repository, pinned to a release tag:

```yaml
jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate deployment plan
        run: databricks bundle plan -t dev -o json > artifacts/plan.json

      - name: Publish deployment plan summary
        uses: Pinnacle-Solutions-Group/gh-actions-toolkit/databricks/render-databricks-plan@v1
        with:
          plan-path: artifacts/plan.json   # relative to the workflow's working directory
          bundle-target: dev               # optional, defaults to "dev"

      # The summary omits raw values. Keep the full plan for auditing.
      - uses: actions/upload-artifact@v4
        with:
          name: databricks-plan
          path: artifacts/plan.json
```

Requirements: a runner with `python3` (3.9 or later) and `bash`. Linux and
macOS runners are supported; Windows runners are not tested.

## Testing

`tests/test_renderer.py` runs `render_plan.py` against the fixtures in
`tests/fixtures/` and checks both the happy-path output and that failures are
reported cleanly (no raw tracebacks).

```bash
python3 databricks/render-databricks-plan/tests/test_renderer.py
```

Run this after any change to `render_plan.py`. CI runs it on every pull request.

## Schema confidence status

The renderer's parsing logic assumes a specific shape for `bundle plan`
JSON output (top-level `plan` object, `resources.<type>.<name>` keys,
`changes.<field>.action` nesting). **Verified** for all four actions
(`create`, `update`, `delete`, `skip`) against real Databricks CLI 1.20.0
output captured from real `create`, `update`, `delete` and `skip` plans.
Fixtures
`03_update_job.json` and `04_delete_job.json` are sanitized copies of
real samples (resource names/paths/timestamps replaced, same
structure).

One schema detail the real samples revealed: a map-field change (e.g. a
new tag) appears as `changes["tags['key_name']"]`, not a bare `changes.tags`
— and update entries use `old`/`new`/`remote` keys, not `local`/`remote` as
originally guessed. Neither affects the renderer, which only reads each
change's `action` field, but keep it in mind if the renderer is ever
extended to show old/new values.

## Fixture reference

| Fixture | Create | Update | Delete | Unchanged | Purpose |
|---|---:|---:|---:|---:|---|
| 01_no_changes.json | 0 | 0 | 0 | 1 | No-op deployment (verified shape) |
| 02_create_job.json | 1 | 0 | 0 | 0 | New resource (verified shape) |
| 03_update_job.json | 0 | 1 | 0 | 0 | Field-level update; sanitized from a real plan (verified shape) |
| 04_delete_job.json | 0 | 0 | 1 | 0 | Resource removal; sanitized from a real plan (verified shape) |
| 05_mixed_changes.json | 1 | 1 | 1 | 1 | All action types in one plan |
| 06_unknown_action.json | - | - | - | - | Unrecognized action → clean failure, not silent misreport |
| 07_malformed_plan.json | - | - | - | - | Invalid JSON syntax → clean failure |
| 08_wrong_plan_shape.json | - | - | - | - | Valid JSON, wrong shape (`"plan": []`) → clean failure, not an unhandled traceback |

## Adding a fixture

1. Add `fixtures/<name>.json`.
2. Add an entry to `fixtures/expected.json`: `expected_counts` (or `null`
   for a failure case) and `expect_success`; failure cases also need
   `expected_error` (a substring that must appear in stderr).
3. Run the test script — it picks up every key in `expected.json`
   automatically.
4. If the fixture is a real captured plan rather than a synthetic one,
   say so in this file's fixture table so the confidence status stays
   accurate.

## Safety note

Never run `databricks bundle deploy --plan` against anything in
`fixtures/` — they use synthetic/invalid lineage and are only valid input
for `render_plan.py`.
