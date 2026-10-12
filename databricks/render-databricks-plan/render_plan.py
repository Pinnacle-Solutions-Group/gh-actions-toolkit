"""
=============================================================
Databricks Deployment Plan - GitHub Actions Summary Renderer
=============================================================

Purpose:
    Converts the JSON output of `databricks bundle plan` into a concise,
    human-readable Markdown summary displayed in GitHub Actions.

    The summary provides:
      - Deployment target and Git commit
      - Create, update, and delete counts
      - Resource-level changes and relevant configuration fields
      - Unchanged resource counts

    The complete JSON plan is not embedded; callers should retain it
    separately (for example as a workflow artifact) for troubleshooting
    and auditing.

Usage:
    python render_plan.py <path-to-plan.json>

Example:
    python render_plan.py artifacts/plan.json >> "$GITHUB_STEP_SUMMARY"

Environment Variables:
    BUNDLE_TARGET: Databricks bundle deployment target (default: dev)
    GITHUB_SHA:    Commit SHA supplied by GitHub Actions (default: local)

Design:
    - Uses Python standard library only; no external dependencies.
    - Does not modify Databricks resources or deployment state.
    - Excludes raw configuration values and internal deployment metadata.
    - Rejects unknown resource actions rather than misreporting changes.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path


# Databricks resource-level actions recognized by this renderer.
SUPPORTED_ACTIONS = {"create", "update", "delete", "skip"}


def clean(value: object) -> str:
    """Escape text for safe inclusion in a Markdown table cell.

    Args:
        value: Value to render as text.

    Returns:
        String with Markdown-sensitive table characters escaped.
    """
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("`", "\\`")
    )


def get_change_details(resource: dict, action: str) -> str:
    """Build a concise description of a planned resource change.

    Args:
        resource: Resource entry from the Databricks JSON plan.
        action: Normalized resource-level action.

    Returns:
        Human-readable change description.

    Notes:
        Only actual field-level changes are included for updates.
        Fields marked 'skip' are ignored because they represent
        unchanged values, empty values, or backend defaults.

        Raw before/after values are intentionally excluded.
    """
    if action == "create":
        return "New resource"

    if action == "delete":
        return "Resource removal"

    if action == "skip":
        return "No changes"

    # For updates, identify fields containing actual changes.
    changes = resource.get("changes", {})
    if not isinstance(changes, dict):
        raise ValueError("Resource 'changes' must be an object")

    changed_fields = []
    for field, change in changes.items():
        if not isinstance(change, dict):
            raise ValueError(f"Change entry '{field}' must be an object")
        if str(change.get("action", "skip")).lower() != "skip":
            changed_fields.append(field)

    return ", ".join(changed_fields) if changed_fields else "Configuration update"


def parse_resource_key(key: str) -> tuple[str, str]:
    """Split a plan resource key into (resource_type, resource_name).

    Args:
        key: Plan resource key, e.g. "resources.jobs.sample_job".

    Returns:
        Tuple of (resource_type, resource_name). Falls back to
        ("unknown", key) if the key doesn't have the expected
        "resources.<type>.<name>" shape.
    """
    parts = key.split(".", 2)
    if len(parts) < 3:
        return "unknown", key
    return parts[1], parts[2]


def parse_resources(plan: dict) -> tuple[list[tuple], Counter]:
    """Extract resource changes and calculate action totals.

    Args:
        plan: Parsed Databricks deployment plan JSON.

    Returns:
        Tuple containing:
          - Resource rows (action, type, name, description)
          - Counter of resource-level actions

    Raises:
        ValueError: If the plan is malformed or an unsupported action
            is encountered.
    """
    resources = plan.get("plan")
    if not isinstance(resources, dict):
        raise ValueError("Plan JSON missing a 'plan' object")

    rows = []
    counts = Counter()

    for key, resource in sorted(resources.items()):
        if not isinstance(resource, dict):
            raise ValueError(f"Plan entry '{key}' must be an object")
        raw_action = resource.get("action")
        if not isinstance(raw_action, str):
            raise ValueError(f"Plan entry '{key}' missing a string 'action'")
        action = raw_action.lower()

        if action not in SUPPORTED_ACTIONS:
            raise ValueError(
                f"Unsupported Databricks plan action: {action}"
            )

        counts[action] += 1

        resource_type, resource_name = parse_resource_key(key)
        detail = get_change_details(resource, action)

        rows.append((action, resource_type, resource_name, detail))

    return rows, counts


def render_summary(rows: list[tuple], counts: Counter) -> None:
    """Write a Markdown deployment summary to standard output.

    Args:
        rows: Parsed resource change rows.
        counts: Resource action totals.

    Notes:
        GitHub Actions captures this output when redirected to
        the GITHUB_STEP_SUMMARY environment file.
    """
    target = os.environ.get("BUNDLE_TARGET", "dev")
    commit_sha = os.environ.get("GITHUB_SHA", "local")

    total_changes = (
        counts["create"]
        + counts["update"]
        + counts["delete"]
    )

    # Deployment identification.
    print("## Databricks Deployment Plan\n")
    print(f"**Target:** `{clean(target)}`  ")
    print(f"**Commit:** `{clean(commit_sha)}`\n")

    # High-level change counts.
    print("| Create | Update | Delete | Total changes |")
    print("|---:|---:|---:|---:|")
    print(
        f"| {counts['create']} "
        f"| {counts['update']} "
        f"| {counts['delete']} "
        f"| {total_changes} |\n"
    )

    # Resource-level change details.
    print("### Resource details\n")
    print("| Action | Resource type | Resource | Relevant change |")
    print("|---|---|---|---|")

    for action, resource_type, name, detail in rows:
        display_action = (
            "No change" if action == "skip" else action.title()
        )

        print(
            f"| {display_action} "
            f"| {clean(resource_type).title()} "
            f"| `{clean(name)}` "
            f"| {clean(detail)} |"
        )

    print(f"\n**Unchanged resources:** {counts['skip']}  ")
    print("\nThis summary omits raw values; see the full JSON plan for detail.")


def main() -> int:
    """Load the deployment plan and generate the Markdown summary.

    Returns:
        0 on success, 1 if processing fails.
    """
    if len(sys.argv) != 2:
        print(
            "Usage: render_plan.py <path-to-plan.json>",
            file=sys.stderr,
        )
        return 1

    try:
        plan_path = Path(sys.argv[1])

        with plan_path.open(encoding="utf-8") as file:
            plan = json.load(file)

        rows, counts = parse_resources(plan)
        render_summary(rows, counts)

        return 0

    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"Error rendering deployment plan: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

