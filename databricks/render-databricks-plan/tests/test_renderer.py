#!/usr/bin/env python3
"""Validate the GitHub Job Summary renderer against synthetic plan fixtures.

Usage (from repository root):
    python3 databricks/render-databricks-plan/tests/test_renderer.py
Requires only Python standard library and the existing renderer.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RENDERER = HERE.parent / 'render_plan.py'
EXPECT = json.loads((HERE / 'fixtures' / 'expected.json').read_text())

_spec = importlib.util.spec_from_file_location('render_plan', RENDERER)
render_plan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render_plan)


def run_renderer(*args, env_overrides=None):
    env = {**os.environ, 'BUNDLE_TARGET': 'dev', 'GITHUB_SHA': 'fixture-commit'}
    env.update(env_overrides or {})
    return subprocess.run(
        [sys.executable, str(RENDERER), *args],
        text=True, capture_output=True, env=env,
    )


def test_fixtures():
    for filename, expected in EXPECT.items():
        result = run_renderer(str(HERE / 'fixtures' / filename))
        success = result.returncode == 0
        assert success == expected['expect_success'], (filename, result.stdout, result.stderr)
        if success:
            counts = expected['expected_counts']
            totals = [counts[a] for a in ('create', 'update', 'delete')]
            totals.append(sum(totals))
            expected_row = '| ' + ' | '.join(map(str, totals)) + ' |'
            assert expected_row in result.stdout, (filename, expected_row, result.stdout)
            assert '**Target:** `dev`' in result.stdout, filename
            assert '**Commit:** `fixture-commit`' in result.stdout, filename
            assert f"**Unchanged resources:** {counts['skip']}" in result.stdout, filename
            if filename == '03_update_job.json':
                assert 'max_concurrent_runs' in result.stdout
            if filename == '05_mixed_changes.json':
                assert '| Create | Jobs |' in result.stdout, result.stdout
                assert '| Update | Jobs |' in result.stdout, result.stdout
                assert '| Delete | Jobs |' in result.stdout, result.stdout
                assert '| No change | Jobs |' in result.stdout, result.stdout
        else:
            # A handled failure must report a clean error, never a raw traceback.
            assert 'Traceback' not in result.stderr, (filename, result.stderr)
            assert expected['expected_error'] in result.stderr, (filename, result.stderr)
        print(f"PASS: {filename}")
    print(f"PASS: {len(EXPECT)} fixture cases")


def test_cli_usage_error():
    # No path argument at all.
    result = run_renderer()
    assert result.returncode == 1
    assert 'Traceback' not in result.stderr
    assert 'Usage:' in result.stderr

    # Too many arguments.
    result = run_renderer('a', 'b')
    assert result.returncode == 1
    assert 'Traceback' not in result.stderr
    assert 'Usage:' in result.stderr
    print("PASS: cli usage errors")


def test_missing_file():
    result = run_renderer(str(HERE / 'fixtures' / 'does_not_exist.json'))
    assert result.returncode == 1
    assert 'Traceback' not in result.stderr
    assert 'Error rendering deployment plan' in result.stderr
    print("PASS: missing file reported cleanly")


def test_clean_escapes_markdown_sensitive_characters():
    assert render_plan.clean('a|b') == 'a\\|b'
    assert render_plan.clean('a\\b') == 'a\\\\b'
    assert render_plan.clean('a`b') == 'a\\`b'
    assert render_plan.clean('a\nb') == 'a b'
    assert render_plan.clean('a\rb') == 'a b'
    assert render_plan.clean(123) == '123'
    print("PASS: clean() escaping")


def test_get_change_details_branches():
    gcd = render_plan.get_change_details

    assert gcd({}, 'create') == 'New resource'
    assert gcd({}, 'delete') == 'Resource removal'
    assert gcd({}, 'skip') == 'No changes'

    resource_with_changes = {
        'changes': {
            'max_concurrent_runs': {'action': 'update'},
            'timeout_seconds': {'action': 'skip'},
        }
    }
    assert gcd(resource_with_changes, 'update') == 'max_concurrent_runs'

    resource_all_skipped = {
        'changes': {'timeout_seconds': {'action': 'skip'}}
    }
    assert gcd(resource_all_skipped, 'update') == 'Configuration update'

    resource_no_changes_key = {}
    assert gcd(resource_no_changes_key, 'update') == 'Configuration update'
    print("PASS: get_change_details() branches")


def test_parse_resource_key():
    prk = render_plan.parse_resource_key

    assert prk('resources.jobs.sample_job') == ('jobs', 'sample_job')
    # Name containing a dot must not be truncated.
    assert prk('resources.jobs.sample.job') == ('jobs', 'sample.job')
    # Malformed / unexpected key shapes fall back to "unknown" rather than
    # guessing, so a schema surprise shows up as a visible label, not
    # silently wrong data in the audit trail.
    assert prk('jobs.sample_job') == ('unknown', 'jobs.sample_job')
    assert prk('sample_job') == ('unknown', 'sample_job')
    print("PASS: parse_resource_key()")


def test_malformed_entries_fail_cleanly(tmp_path=None):
    import tempfile
    cases = {
        'missing action': {'plan': {'resources.jobs.a': {}}},
        'non-string action': {'plan': {'resources.jobs.a': {'action': 1}}},
        'entry not object': {'plan': {'resources.jobs.a': 'update'}},
        'changes not object': {'plan': {'resources.jobs.a': {'action': 'update', 'changes': []}}},
        'change not object': {'plan': {'resources.jobs.a': {'action': 'update', 'changes': {'f': 'x'}}}},
    }
    with tempfile.TemporaryDirectory() as d:
        for name, plan in cases.items():
            path = Path(d) / 'plan.json'
            path.write_text(json.dumps(plan))
            result = run_renderer(str(path))
            assert result.returncode == 1, (name, result.stdout)
            assert 'Traceback' not in result.stderr, (name, result.stderr)
            assert 'Error rendering deployment plan' in result.stderr, name
    print("PASS: malformed entries fail cleanly")


def main():
    if not RENDERER.is_file():
        raise FileNotFoundError(f'Renderer not found: {RENDERER}')

    test_fixtures()
    test_cli_usage_error()
    test_missing_file()
    test_malformed_entries_fail_cleanly()
    test_clean_escapes_markdown_sensitive_characters()
    test_get_change_details_branches()
    test_parse_resource_key()

    print("ALL PASS")


if __name__ == '__main__':
    main()
