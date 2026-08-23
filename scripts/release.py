#!/usr/bin/env python3
"""Owner-local release gate and GitHub source-release route.

The release manifest is the target-specific source of truth. Keeping the
route manifest-driven means a later patch release can reuse the same checks
without changing this script or accidentally reusing an older tag.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPOSITORY = "8Dionysus/aoa-course-connector"
MANIFEST = "release/release-manifest.json"
MANIFEST_SCHEMA = "aoa_course_connector_release_manifest_v1"
SEMVER_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")
REQUIRED_VERSION_SOURCES = {
    "pyproject.toml",
    "src/aoa_course_connector/__init__.py",
    "src/aoa_course_connector/mcp/server.py",
    "CHANGELOG.md",
}


class ReleaseError(RuntimeError):
    """A release gate or publication step failed."""


@dataclass(frozen=True)
class ReleaseConfig:
    """Target-specific release identity loaded from the owner manifest."""

    manifest_path: str
    payload: dict[str, Any]
    repository: str
    version: str
    tag: str
    canonical_changelog: str
    reconciliation_ledger: str
    version_sources: tuple[str, ...]
    provider_prerequisites: tuple[tuple[str, str, str], ...]
    workflow_pins: dict[str, Any]
    publication: dict[str, Any]
    previous_release: dict[str, Any] | None

    @property
    def version_tuple(self) -> tuple[int, int, int]:
        match = SEMVER_RE.fullmatch(self.version)
        if match is None:
            raise ReleaseError(f"release manifest version is not stable SemVer: {self.version!r}")
        return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ReleaseError(f"release manifest {key} must be a non-empty string")
    return value


def load_release_config(root: Path, manifest_path: str = MANIFEST) -> ReleaseConfig:
    """Load and minimally shape one target release manifest."""

    path = root / manifest_path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"release manifest unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseError("release manifest must be a JSON object")

    repository = _require_string(payload, "repository")
    version = _require_string(payload, "version")
    tag = _require_string(payload, "tag")
    canonical_changelog = _require_string(payload, "canonical_changelog")
    reconciliation_ledger = _require_string(payload, "reconciliation_ledger")

    version_sources_raw = payload.get("version_sources")
    if not isinstance(version_sources_raw, list) or not all(isinstance(item, str) for item in version_sources_raw):
        raise ReleaseError("release manifest version_sources must be a list of paths")

    providers_raw = payload.get("provider_prerequisites")
    if not isinstance(providers_raw, list):
        raise ReleaseError("release manifest provider_prerequisites must be a list")
    providers: list[tuple[str, str, str]] = []
    for item in providers_raw:
        if not isinstance(item, dict):
            raise ReleaseError("release manifest provider prerequisite must be an object")
        providers.append((_require_string(item, "repository"), _require_string(item, "tag"), _require_string(item, "commit")))

    workflow_pins = payload.get("workflow_pins")
    if not isinstance(workflow_pins, dict):
        raise ReleaseError("release manifest workflow_pins must be an object")
    publication = payload.get("publication")
    if not isinstance(publication, dict):
        raise ReleaseError("release manifest publication must be an object")
    previous_release = payload.get("previous_release")
    if previous_release is not None and not isinstance(previous_release, dict):
        raise ReleaseError("release manifest previous_release must be an object when present")

    return ReleaseConfig(
        manifest_path=manifest_path,
        payload=payload,
        repository=repository,
        version=version,
        tag=tag,
        canonical_changelog=canonical_changelog,
        reconciliation_ledger=reconciliation_ledger,
        version_sources=tuple(version_sources_raw),
        provider_prerequisites=tuple(providers),
        workflow_pins=workflow_pins,
        publication=publication,
        previous_release=previous_release,
    )


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


def changelog_notes(root: Path, config: ReleaseConfig) -> str:
    path = root / config.canonical_changelog
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    marker = f"## {config.version} - "
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


def check_manifest(root: Path, config: ReleaseConfig, errors: list[str], checks: dict[str, Any]) -> None:
    payload = config.payload
    checks["manifest"] = {
        "path": config.manifest_path,
        "schema_version": payload.get("schema_version"),
        "version": config.version,
        "tag": config.tag,
        "previous_release": config.previous_release,
    }
    expected = {
        "schema_version": MANIFEST_SCHEMA,
        "repository": REPOSITORY,
        "canonical_changelog": "CHANGELOG.md",
        "reconciliation_ledger": f"docs/RELEASE_RECONCILIATION_{config.version}.md",
        "tag": f"v{config.version}",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            errors.append(f"release manifest {key} mismatch: {payload.get(key)!r}")
    try:
        target_tuple = config.version_tuple
    except ReleaseError as exc:
        errors.append(str(exc))
        target_tuple = None
    if config.version_sources and not REQUIRED_VERSION_SOURCES.issubset(set(config.version_sources)):
        missing = sorted(REQUIRED_VERSION_SOURCES.difference(config.version_sources))
        errors.append(f"release manifest version_sources missing required paths: {missing}")
    if target_tuple is not None and target_tuple > (0, 1, 0) and config.previous_release is None:
        errors.append("release manifest must identify the previous stable release for sequential releases")
    publication_kind = config.publication.get("kind")
    if publication_kind != "github_source_release":
        errors.append(f"unsupported publication kind: {publication_kind!r}")
    if config.publication.get("assets") != []:
        errors.append("source-only release must declare an empty assets list")
    package_registry = config.publication.get("package_registry")
    if not isinstance(package_registry, dict) or package_registry.get("published") is not False:
        errors.append("source-only release must declare package_registry.published=false")


def check_version_markers(root: Path, config: ReleaseConfig, errors: list[str], checks: dict[str, Any]) -> None:
    version = re.escape(config.version)
    patterns = {
        "pyproject.toml": re.compile(rf'^version\s*=\s*["\']{version}["\']$', re.MULTILINE),
        "src/aoa_course_connector/__init__.py": re.compile(rf'^__version__\s*=\s*["\']{version}["\']$', re.MULTILINE),
        "src/aoa_course_connector/mcp/server.py": re.compile(rf'^SERVER_VERSION\s*=\s*["\']{version}["\']$', re.MULTILINE),
        "CHANGELOG.md": re.compile(rf'^## {version} - (?!Unreleased$).+', re.MULTILINE),
    }
    for relative in config.version_sources:
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (FileNotFoundError, UnicodeDecodeError) as exc:
            checks[f"version:{relative}"] = False
            errors.append(f"version source unreadable: {relative}: {exc}")
            continue
        pattern = patterns.get(relative)
        matched = bool(pattern.search(text)) if pattern is not None else config.version in text
        checks[f"version:{relative}"] = matched
        if not matched:
            errors.append(f"version marker mismatch: {relative}")


def _workflow_pin(config: ReleaseConfig, key: str, field: str = "ref") -> str | None:
    value = config.workflow_pins.get(key)
    if not isinstance(value, dict):
        return None
    ref = value.get(field)
    return ref if isinstance(ref, str) and ref else None


def check_workflow_pins(root: Path, config: ReleaseConfig, errors: list[str], checks: dict[str, Any]) -> None:
    text = (root / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    kag_pin = _workflow_pin(config, "aoa_kag_repo_local_action")
    stats_pin = _workflow_pin(config, "aoa_stats_checkout")
    kag_ok = kag_pin is not None and kag_pin in text
    stats_ok = stats_pin is not None and stats_pin in text
    checks["workflow_pins"] = {
        "aoa_kag_action": kag_pin if kag_ok else None,
        "aoa_stats_checkout": stats_pin if stats_ok else None,
    }
    if not kag_ok:
        errors.append("workflow KAG action pin is missing or differs from the release manifest")
    if not stats_ok:
        errors.append("workflow aoa-stats checkout pin is missing or differs from the release manifest")


def check_provider_releases(root: Path, config: ReleaseConfig, errors: list[str], checks: dict[str, Any]) -> None:
    provider_results: dict[str, Any] = {}
    for repository, tag, expected_commit in config.provider_prerequisites:
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


def check_course_baseline(root: Path, config: ReleaseConfig, errors: list[str], checks: dict[str, Any]) -> None:
    head = current_commit(root)
    origin = remote_main(root)
    clean = git(root, "status", "--porcelain=v1") == ""
    github_main_payload = gh_json(root, f"repos/{config.repository}/branches/main")
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


def check_previous_release(root: Path, config: ReleaseConfig, errors: list[str], checks: dict[str, Any]) -> None:
    previous = config.previous_release
    if previous is None:
        checks["previous_release"] = {"present": False}
        return
    try:
        previous_version = _require_string(previous, "version")
        previous_tag = _require_string(previous, "tag")
        previous_commit = _require_string(previous, "commit")
        previous_tuple = tuple(int(part) for part in previous_version.split("."))
    except (ReleaseError, ValueError) as exc:
        errors.append(f"invalid previous_release metadata: {exc}")
        return
    valid_previous_tuple = len(previous_tuple) == 3
    if not valid_previous_tuple or previous_tuple >= config.version_tuple:
        errors.append(f"previous release must precede target {config.version}: {previous_version}")
    if previous_tag != f"v{previous_version}":
        errors.append(f"previous release tag mismatch: {previous_tag!r}")
    resolved = tag_commit(root, config.repository, previous_tag)
    release = maybe_gh_json(root, f"repos/{config.repository}/releases/tags/{previous_tag}")
    stable = isinstance(release, dict) and not release.get("draft") and not release.get("prerelease")
    head = current_commit(root)
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", previous_commit, head],
        cwd=root,
        check=False,
    ).returncode == 0
    checks["previous_release"] = {
        "version": previous_version,
        "tag": previous_tag,
        "declared_commit": previous_commit,
        "resolved_commit": resolved,
        "stable_release": stable,
        "current_head_contains_previous": ancestor,
    }
    if resolved != previous_commit:
        errors.append(f"previous release tag moved: {previous_tag} -> {resolved!r}, expected {previous_commit}")
    if not stable:
        errors.append(f"previous release is not stable/published: {previous_tag}")
    if not ancestor:
        errors.append(f"current release source is not based on previous release {previous_tag}")


def check_no_course_release(root: Path, config: ReleaseConfig, errors: list[str], checks: dict[str, Any]) -> None:
    existing_tag = tag_commit(root, config.repository, config.tag)
    release = maybe_gh_json(root, f"repos/{config.repository}/releases/tags/{config.tag}")
    checks["course_release_absent"] = {"tag": existing_tag, "release_present": isinstance(release, dict)}
    if existing_tag is not None:
        errors.append(f"target tag already exists before publication: {config.tag} -> {existing_tag}")
    if isinstance(release, dict):
        errors.append(f"target release already exists before publication: {config.tag}")


def collect_preflight(
    root: Path,
    *,
    manifest_path: str = MANIFEST,
    require_absent: bool = True,
) -> tuple[list[str], dict[str, Any], ReleaseConfig | None]:
    errors: list[str] = []
    checks: dict[str, Any] = {}
    try:
        config = load_release_config(root, manifest_path)
    except ReleaseError as exc:
        errors.append(str(exc))
        return errors, checks, None
    check_manifest(root, config, errors, checks)
    check_version_markers(root, config, errors, checks)
    check_workflow_pins(root, config, errors, checks)
    check_provider_releases(root, config, errors, checks)
    check_course_baseline(root, config, errors, checks)
    check_previous_release(root, config, errors, checks)
    if require_absent:
        check_no_course_release(root, config, errors, checks)
    return errors, checks, config


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def preflight(root: Path, manifest_path: str = MANIFEST) -> int:
    errors, checks, config = collect_preflight(root, manifest_path=manifest_path)
    emit(
        {
            "schema": "aoa_course_connector_release_preflight_v1",
            "status": "ok" if not errors else "error",
            "errors": errors,
            "release": {"version": config.version, "tag": config.tag} if config else None,
            "checks": checks,
        }
    )
    return 0 if not errors else 1


def dry_run(root: Path, expected_commit: str, manifest_path: str = MANIFEST) -> int:
    errors, checks, config = collect_preflight(root, manifest_path=manifest_path)
    head = current_commit(root)
    if head != expected_commit:
        errors.append(f"dry-run commit mismatch: HEAD {head} != requested {expected_commit}")
    notes = ""
    if config is not None:
        try:
            notes = changelog_notes(root, config)
        except ReleaseError as exc:
            errors.append(str(exc))
    checks["dry_run"] = {"commit": expected_commit, "notes_sha256": sha256_text(notes) if notes else None}
    emit(
        {
            "schema": "aoa_course_connector_release_dry_run_v1",
            "status": "ok" if not errors else "error",
            "errors": errors,
            "checks": checks,
            "planned": {
                "repository": config.repository if config else REPOSITORY,
                "version": config.version if config else None,
                "tag": config.tag if config else None,
                "commit": expected_commit,
                "assets": [],
            },
        }
    )
    return 0 if not errors else 1


def publish(root: Path, expected_commit: str, manifest_path: str = MANIFEST) -> int:
    if current_commit(root) != expected_commit:
        raise ReleaseError("publish requires HEAD to be the requested exact landed commit")
    errors, checks, config = collect_preflight(root, manifest_path=manifest_path)
    if errors or config is None:
        emit({"schema": "aoa_course_connector_release_publish_v1", "status": "error", "errors": errors, "checks": checks})
        return 1
    notes = changelog_notes(root, config)
    ref = maybe_gh_json(root, f"repos/{config.repository}/git/ref/tags/{config.tag}")
    existing_release = maybe_gh_json(root, f"repos/{config.repository}/releases/tags/{config.tag}")
    if existing_release is not None:
        raise ReleaseError(f"target GitHub Release already exists: {config.tag}")
    if ref is None:
        gh(root, "api", "-X", "POST", f"repos/{config.repository}/git/refs", "-f", f"ref=refs/tags/{config.tag}", "-f", f"sha={expected_commit}")
    elif tag_commit(root, config.repository, config.tag) != expected_commit:
        raise ReleaseError("existing target tag does not identify the landed commit")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md") as notes_file:
        notes_file.write(notes)
        notes_file.flush()
        gh(
            root,
            "release",
            "create",
            config.tag,
            "--repo",
            config.repository,
            "--title",
            f"aoa-course-connector {config.tag}",
            "--verify-tag",
            "--notes-file",
            notes_file.name,
        )
    emit(
        {
            "schema": "aoa_course_connector_release_publish_v1",
            "status": "ok",
            "repository": config.repository,
            "version": config.version,
            "tag": config.tag,
            "commit": expected_commit,
            "notes_sha256": sha256_text(notes),
            "assets": [],
        }
    )
    return 0


def postpublish(root: Path, expected_commit: str, manifest_path: str = MANIFEST) -> int:
    errors, checks, config = collect_preflight(root, manifest_path=manifest_path, require_absent=False)
    if config is None:
        emit({"schema": "aoa_course_connector_release_postpublish_v1", "status": "error", "errors": errors, "checks": checks})
        return 1
    if current_commit(root) != expected_commit:
        errors.append(f"postpublish HEAD mismatch: {current_commit(root)} != {expected_commit}")
    resolved = tag_commit(root, config.repository, config.tag)
    release = maybe_gh_json(root, f"repos/{config.repository}/releases/tags/{config.tag}")
    notes = changelog_notes(root, config)
    body = release.get("body") if isinstance(release, dict) else None
    stable = isinstance(release, dict) and not release.get("draft") and not release.get("prerelease")
    latest_rows = json.loads(
        gh(
            root,
            "release",
            "list",
            "--repo",
            config.repository,
            "--limit",
            "20",
            "--json",
            "tagName,isLatest,isDraft,isPrerelease,publishedAt",
        )
    )
    latest = next((row for row in latest_rows if row.get("tagName") == config.tag), None)
    checks["postpublish"] = {
        "tag_commit": resolved,
        "release_stable": stable,
        "release_body_sha256": sha256_text(body) if isinstance(body, str) else None,
        "canonical_notes_sha256": sha256_text(notes),
        "latest_marker": latest,
        "release_url": release.get("html_url") if isinstance(release, dict) else None,
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
    emit(
        {
            "schema": "aoa_course_connector_release_postpublish_v1",
            "status": "ok" if not errors else "error",
            "errors": errors,
            "release": {"version": config.version, "tag": config.tag},
            "checks": checks,
        }
    )
    return 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", default=MANIFEST, help="Target release manifest path relative to --repo-root.")
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
            return preflight(root, args.manifest)
        if args.action == "dry-run":
            return dry_run(root, args.commit, args.manifest)
        if args.action == "publish":
            if not args.confirm:
                raise ReleaseError("publish requires --confirm")
            return publish(root, args.commit, args.manifest)
        return postpublish(root, args.commit, args.manifest)
    except ReleaseError as exc:
        emit({"schema": "aoa_course_connector_release_route_error_v1", "status": "error", "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
