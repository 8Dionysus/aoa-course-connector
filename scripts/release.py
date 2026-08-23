#!/usr/bin/env python3
"""Owner-local release gate and GitHub source-release route."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPOSITORY = "8Dionysus/aoa-course-connector"
VERSION = "0.1.0"
TAG = "v0.1.0"
MANIFEST = "release/release-manifest.json"
EXPECTED_PROVIDER_COMMITS = {
    "8Dionysus/aoa-kag": ("v0.5.0", "813a7f69dc96ec031dad9b897a6991792cc48b7a"),
    "8Dionysus/aoa-stats": ("v0.2.0", "dc608fd5de3fcaf0301f356c9efd52e2bdd350ce"),
}
EXPECTED_KAG_ACTION = "6a79e62c7d20b6b11406dee78f409ada4a51bb3f"
EXPECTED_STATS_CHECKOUT = "dc608fd5de3fcaf0301f356c9efd52e2bdd350ce"


class ReleaseError(RuntimeError):
    """A release gate or publication step failed."""


def command(args: list[str], cwd: Path, *, check: bool = True) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ReleaseError(f"command failed ({' '.join(args[:3])}...): {detail[:1000]}")
    return result.stdout.strip()


def git(root: Path, *args: str) -> str:
    return command(["git", *args], root)


def gh(root: Path, *args: str) -> str:
    return command(["gh", *args], root)


def gh_json(root: Path, endpoint: str) -> Any:
    return json.loads(gh(root, "api", endpoint))


def maybe_gh_json(root: Path, endpoint: str) -> Any | None:
    try:
        return gh_json(root, endpoint)
    except ReleaseError as exc:
        if "404" in str(exc):
            return None
        raise
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"GitHub returned invalid JSON for {endpoint}: {exc}") from exc


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def current_commit(root: Path) -> str:
    return git(root, "rev-parse", "HEAD^{commit}")


def remote_main(root: Path) -> str:
    return git(root, "rev-parse", "origin/main^{commit}")


def changelog_notes(root: Path) -> str:
    path = root / "CHANGELOG.md"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    marker = f"## {VERSION} - "
    start = next((index for index, line in enumerate(lines) if line.startswith(marker)), None)
    if start is None:
        raise ReleaseError(f"canonical changelog section is missing: {marker!r}")
    if "Unreleased" in lines[start]:
        raise ReleaseError("canonical changelog section is still Unreleased")
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    notes = "".join(lines[start + 1 : end]).strip()
    if not notes:
        raise ReleaseError("canonical changelog section has no release notes")
    return notes + "\n"


def tag_commit(root: Path, repository: str, tag: str) -> str | None:
    ref = maybe_gh_json(root, f"repos/{repository}/git/ref/tags/{tag}")
    if not isinstance(ref, dict):
        return None
    obj = ref.get("object")
    if not isinstance(obj, dict):
        raise ReleaseError(f"tag ref has no object: {repository}@{tag}")
    if obj.get("type") == "tag":
        annotated = gh_json(root, f"repos/{repository}/git/tags/{obj['sha']}")
        obj = annotated.get("object")
    if not isinstance(obj, dict) or obj.get("type") != "commit":
        raise ReleaseError(f"tag does not resolve to a commit: {repository}@{tag}")
    return str(obj["sha"])


def check_manifest(root: Path, errors: list[str], checks: dict[str, Any]) -> None:
    path = root / MANIFEST
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        errors.append(f"release manifest unreadable: {exc}")
        return
    checks["manifest"] = {"path": MANIFEST, "schema_version": payload.get("schema_version")}
    expected = {
        "schema_version": "aoa_course_connector_release_manifest_v1",
        "repository": REPOSITORY,
        "version": VERSION,
        "tag": TAG,
        "canonical_changelog": "CHANGELOG.md",
        "reconciliation_ledger": "docs/RELEASE_RECONCILIATION_0.1.0.md",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            errors.append(f"release manifest {key} mismatch: {payload.get(key)!r}")
    providers = {
        item.get("repository"): (item.get("tag"), item.get("commit"))
        for item in payload.get("provider_prerequisites", [])
        if isinstance(item, dict)
    }
    for repository, expected_value in EXPECTED_PROVIDER_COMMITS.items():
        if providers.get(repository) != expected_value:
            errors.append(f"release manifest provider pin mismatch: {repository}")


def check_version_markers(root: Path, errors: list[str], checks: dict[str, Any]) -> None:
    paths = {
        "pyproject.toml": re.compile(r'^version\s*=\s*["\']0\.1\.0["\']$', re.MULTILINE),
        "src/aoa_course_connector/__init__.py": re.compile(r'^__version__\s*=\s*["\']0\.1\.0["\']$', re.MULTILINE),
        "src/aoa_course_connector/mcp/server.py": re.compile(r'^SERVER_VERSION\s*=\s*["\']0\.1\.0["\']$', re.MULTILINE),
        "CHANGELOG.md": re.compile(r'^## 0\.1\.0 - (?!Unreleased$).+', re.MULTILINE),
    }
    for relative, pattern in paths.items():
        text = (root / relative).read_text(encoding="utf-8")
        matched = bool(pattern.search(text))
        checks[f"version:{relative}"] = matched
        if not matched:
            errors.append(f"version marker mismatch: {relative}")


def check_workflow_pins(root: Path, errors: list[str], checks: dict[str, Any]) -> None:
    text = (root / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    kag_ok = EXPECTED_KAG_ACTION in text
    stats_ok = EXPECTED_STATS_CHECKOUT in text
    checks["workflow_pins"] = {
        "aoa_kag_action": EXPECTED_KAG_ACTION if kag_ok else None,
        "aoa_stats_checkout": EXPECTED_STATS_CHECKOUT if stats_ok else None,
    }
    if not kag_ok:
        errors.append("workflow KAG action pin is not the accepted #186 helper")
    if not stats_ok:
        errors.append("workflow aoa-stats checkout is not the v0.2.0 target commit")


def check_provider_releases(root: Path, errors: list[str], checks: dict[str, Any]) -> None:
    provider_results: dict[str, Any] = {}
    for repository, (tag, expected_commit) in EXPECTED_PROVIDER_COMMITS.items():
        resolved = tag_commit(root, repository, tag)
        release = maybe_gh_json(root, f"repos/{repository}/releases/tags/{tag}")
        stable = isinstance(release, dict) and not release.get("draft") and not release.get("prerelease")
        provider_results[repository] = {
            "tag": tag,
            "resolved_commit": resolved,
            "expected_commit": expected_commit,
            "stable_release": stable,
        }
        if resolved != expected_commit:
            errors.append(f"provider tag mismatch: {repository}@{tag} -> {resolved!r}")
        if not stable:
            errors.append(f"provider release is not stable/published: {repository}@{tag}")
    checks["provider_releases"] = provider_results


def check_course_baseline(root: Path, errors: list[str], checks: dict[str, Any]) -> None:
    head = current_commit(root)
    origin = remote_main(root)
    clean = git(root, "status", "--porcelain=v1") == ""
    github_main_payload = gh_json(root, f"repos/{REPOSITORY}/branches/main")
    github_main = str(((github_main_payload.get("commit") or {}).get("sha")))
    base_is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", origin, head],
        cwd=root,
        check=False,
    ).returncode == 0
    checks["git"] = {
        "head": head,
        "origin_main": origin,
        "github_main": github_main,
        "clean": clean,
        "origin_main_is_ancestor": base_is_ancestor,
    }
    if not clean:
        errors.append("release source worktree is dirty")
    if github_main != origin:
        errors.append(f"local origin/main is stale against GitHub: {origin} != {github_main}")
    if not base_is_ancestor:
        errors.append("release source is not based on current origin/main")


def check_no_course_release(root: Path, errors: list[str], checks: dict[str, Any]) -> None:
    existing_tag = tag_commit(root, REPOSITORY, TAG)
    release = maybe_gh_json(root, f"repos/{REPOSITORY}/releases/tags/{TAG}")
    checks["course_release_absent"] = {"tag": existing_tag, "release_present": isinstance(release, dict)}
    if existing_tag is not None:
        errors.append(f"target tag already exists before publication: {TAG} -> {existing_tag}")
    if isinstance(release, dict):
        errors.append(f"target release already exists before publication: {TAG}")


def collect_preflight(root: Path, *, require_absent: bool = True) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    checks: dict[str, Any] = {}
    check_manifest(root, errors, checks)
    check_version_markers(root, errors, checks)
    check_workflow_pins(root, errors, checks)
    check_provider_releases(root, errors, checks)
    check_course_baseline(root, errors, checks)
    if require_absent:
        check_no_course_release(root, errors, checks)
    return errors, checks


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def preflight(root: Path) -> int:
    errors, checks = collect_preflight(root)
    emit({"schema": "aoa_course_connector_release_preflight_v1", "status": "ok" if not errors else "error", "errors": errors, "checks": checks})
    return 0 if not errors else 1


def dry_run(root: Path, expected_commit: str) -> int:
    errors, checks = collect_preflight(root)
    head = current_commit(root)
    if head != expected_commit:
        errors.append(f"dry-run commit mismatch: HEAD {head} != requested {expected_commit}")
    notes = ""
    try:
        notes = changelog_notes(root)
    except ReleaseError as exc:
        errors.append(str(exc))
    checks["dry_run"] = {"commit": expected_commit, "notes_sha256": sha256_text(notes) if notes else None}
    emit({"schema": "aoa_course_connector_release_dry_run_v1", "status": "ok" if not errors else "error", "errors": errors, "checks": checks, "planned": {"repository": REPOSITORY, "tag": TAG, "commit": expected_commit, "assets": []}})
    return 0 if not errors else 1


def publish(root: Path, expected_commit: str) -> int:
    if current_commit(root) != expected_commit:
        raise ReleaseError("publish requires HEAD to be the requested exact landed commit")
    errors, checks = collect_preflight(root)
    if errors:
        emit({"schema": "aoa_course_connector_release_publish_v1", "status": "error", "errors": errors, "checks": checks})
        return 1
    notes = changelog_notes(root)
    ref = maybe_gh_json(root, f"repos/{REPOSITORY}/git/ref/tags/{TAG}")
    if ref is None:
        gh(root, "api", "-X", "POST", f"repos/{REPOSITORY}/git/refs", "-f", f"ref=refs/tags/{TAG}", "-f", f"sha={expected_commit}")
    elif tag_commit(root, REPOSITORY, TAG) != expected_commit:
        raise ReleaseError("existing target tag does not identify the landed commit")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md") as notes_file:
        notes_file.write(notes)
        notes_file.flush()
        gh(root, "release", "create", TAG, "--repo", REPOSITORY, "--title", f"aoa-course-connector {TAG}", "--verify-tag", "--notes-file", notes_file.name)
    emit({"schema": "aoa_course_connector_release_publish_v1", "status": "ok", "repository": REPOSITORY, "tag": TAG, "commit": expected_commit, "notes_sha256": sha256_text(notes), "assets": []})
    return 0


def postpublish(root: Path, expected_commit: str) -> int:
    errors, checks = collect_preflight(root, require_absent=False)
    if current_commit(root) != expected_commit:
        errors.append(f"postpublish HEAD mismatch: {current_commit(root)} != {expected_commit}")
    resolved = tag_commit(root, REPOSITORY, TAG)
    release = maybe_gh_json(root, f"repos/{REPOSITORY}/releases/tags/{TAG}")
    notes = changelog_notes(root)
    body = release.get("body") if isinstance(release, dict) else None
    stable = isinstance(release, dict) and not release.get("draft") and not release.get("prerelease")
    latest_rows = json.loads(gh(root, "release", "list", "--repo", REPOSITORY, "--limit", "20", "--json", "tagName,isLatest,isDraft,isPrerelease,publishedAt"))
    latest = next((row for row in latest_rows if row.get("tagName") == TAG), None)
    checks["postpublish"] = {
        "tag_commit": resolved,
        "release_stable": stable,
        "release_body_sha256": sha256_text(body) if isinstance(body, str) else None,
        "canonical_notes_sha256": sha256_text(notes),
        "latest_marker": latest,
        "assets": (release or {}).get("assets", []) if isinstance(release, dict) else None,
    }
    if resolved != expected_commit:
        errors.append(f"published tag does not identify landed main: {resolved!r} != {expected_commit}")
    if not stable:
        errors.append("published GitHub Release is not stable")
    if body != notes:
        errors.append("published Release body differs from canonical changelog section")
    if not isinstance(latest, dict) or not latest.get("isLatest"):
        errors.append("published Release is not the GitHub latest marker")
    if isinstance(release, dict) and release.get("assets"):
        errors.append("unexpected release assets on source-only publication")
    emit({"schema": "aoa_course_connector_release_postpublish_v1", "status": "ok" if not errors else "error", "errors": errors, "checks": checks})
    return 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("preflight")
    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--commit", required=True)
    pub = subparsers.add_parser("publish")
    pub.add_argument("--commit", required=True)
    pub.add_argument("--confirm", action="store_true")
    post = subparsers.add_parser("postpublish")
    post.add_argument("--commit", required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    try:
        if args.action == "preflight":
            return preflight(root)
        if args.action == "dry-run":
            return dry_run(root, args.commit)
        if args.action == "publish":
            if not args.confirm:
                raise ReleaseError("publish requires --confirm")
            return publish(root, args.commit)
        return postpublish(root, args.commit)
    except ReleaseError as exc:
        emit({"schema": "aoa_course_connector_release_route_error_v1", "status": "error", "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
