"""Deterministic local keyword index for normalized course content."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.storage import run_artifact_dir, run_data_dir


TOKEN_RE = re.compile(r"[\w.+#/-]+", re.UNICODE)


def build_keyword_index(roots: StorageRoots, run_id: str = "starter-fixture") -> Path:
    bundle_path = run_data_dir(roots, run_id) / "normalized" / "course_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    docs = list(_iter_docs(bundle))
    inverted: dict[str, list[dict[str, object]]] = defaultdict(list)
    for doc in docs:
        counts = Counter(tokenize(str(doc.get("text") or "")))
        for term, count in sorted(counts.items()):
            inverted[term].append({"doc_id": doc["doc_id"], "count": count})
    output_dir = run_artifact_dir(roots, run_id) / "indexes"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "keyword_index.json"
    payload = {
        "schema": "aoa_course_keyword_index_v1",
        "run_id": run_id,
        "built_at": _now(),
        "unit": "course_knowledge_item",
        "doc_count": len(docs),
        "term_count": len(inverted),
        "docs": docs,
        "inverted": dict(inverted),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text) if token.strip()]


def _iter_docs(bundle: dict[str, object]) -> list[dict[str, object]]:
    docs: list[dict[str, object]] = []
    for course in bundle.get("courses", []):
        if not isinstance(course, dict):
            continue
        course_path = [str(course.get("title") or course.get("course_id"))]
        for module in course.get("modules", []):
            if not isinstance(module, dict):
                continue
            module_path = [*course_path, str(module.get("title") or module.get("module_id"))]
            for lesson in module.get("lessons", []):
                if not isinstance(lesson, dict):
                    continue
                lesson_path = [*module_path, str(lesson.get("title") or lesson.get("lesson_id"))]
                lesson_evidence = lesson.get("evidence", {}) if isinstance(lesson.get("evidence"), dict) else {}
                for step in lesson.get("steps", []):
                    if isinstance(step, dict):
                        docs.append(_doc("step", step.get("step_id"), step.get("text"), course, module, lesson, lesson_path, step.get("evidence") or lesson_evidence))
                for transcript in lesson.get("transcripts", []):
                    if isinstance(transcript, dict):
                        docs.append(_doc("transcript", transcript.get("transcript_id"), transcript.get("text"), course, module, lesson, lesson_path, transcript.get("evidence") or lesson_evidence))
                for assignment in lesson.get("assignments", []):
                    if isinstance(assignment, dict):
                        docs.append(_doc("assignment", assignment.get("assignment_id"), assignment.get("prompt"), course, module, lesson, lesson_path, assignment.get("evidence") or lesson_evidence))
                for thread in lesson.get("comment_threads", []):
                    if not isinstance(thread, dict):
                        continue
                    for comment in thread.get("comments", []):
                        if isinstance(comment, dict):
                            docs.append(_doc("comment", comment.get("comment_id"), comment.get("text"), course, module, lesson, lesson_path, comment.get("evidence") or lesson_evidence))
                for asset in lesson.get("assets", []):
                    if isinstance(asset, dict):
                        text = f"{asset.get('title', '')} {asset.get('kind', '')} {asset.get('download_state', '')}"
                        docs.append(_doc("asset", asset.get("asset_id"), text, course, module, lesson, lesson_path, asset.get("evidence") or lesson_evidence))
    return docs


def _doc(kind: str, item_id: object, text: object, course: dict[str, object], module: dict[str, object], lesson: dict[str, object], path: list[str], evidence: object) -> dict[str, object]:
    evidence_dict = evidence if isinstance(evidence, dict) else {}
    doc_id = f"{kind}:{item_id}"
    return {
        "doc_id": doc_id,
        "kind": kind,
        "course_id": course.get("course_id"),
        "course_title": course.get("title"),
        "module_id": module.get("module_id"),
        "module_title": module.get("title"),
        "lesson_id": lesson.get("lesson_id"),
        "lesson_title": lesson.get("title"),
        "lesson_url": lesson.get("url"),
        "path": path,
        "text": str(text or ""),
        "tokens": len(tokenize(str(text or ""))),
        "platform": course.get("platform"),
        "freshness_state": lesson.get("freshness_state", "unknown"),
        "source_url": evidence_dict.get("source_url") or lesson.get("url"),
        "fetched_at": evidence_dict.get("fetched_at"),
        "evidence_id": evidence_dict.get("evidence_id"),
    }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
