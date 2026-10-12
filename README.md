# gh-actions-toolkit

Reusable GitHub composite actions, grouped by domain.

## Actions

| Action | Description |
|---|---|
| [databricks/render-databricks-plan](databricks/render-databricks-plan) | Render `databricks bundle plan -o json` as a job summary |

## Using an action

Reference an action by its path in this repository and pin a release tag:

```yaml
- uses: Pinnacle-Solutions-Group/gh-actions-toolkit/<domain>/<action>@v1
  with:
    # inputs documented in each action's README
```

See [GitHub's docs on workflow syntax](https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idstepsuses)
for the `uses` reference format. For stronger supply-chain guarantees,
pin to a full commit SHA instead of a tag.

## Layout and conventions

```
<domain>/<action-name>/
  action.yml     # composite action definition
  README.md      # inputs, usage, behavior
  tests/         # tests/test_*.py, run by CI
```

- Actions are self-contained; no shared code between actions.
- Pass all `inputs.*` values to scripts through `env:`, never by
  interpolating `${{ }}` into a `run:` script (prevents script injection).
- Each action ships tests under `tests/`. CI runs every `*/*/tests/test_*.py`.

## Versioning

Releases use repo-wide semantic version tags (`v1.2.3`) with a floating
major tag (`v1`) moved to the latest `v1.x.y`. A breaking change to any
action's inputs or behavior requires a new major version. If one action
later needs to version independently, tag it with a path prefix, for
example `databricks/render-databricks-plan/v2`.

## License

MIT. See [LICENSE](LICENSE).
