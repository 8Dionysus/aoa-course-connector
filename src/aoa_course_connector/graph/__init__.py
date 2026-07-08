"""Build a course knowledge graph from normalized course bundles."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.storage import run_artifact_dir, run_data_dir


def build_graph(roots: StorageRoots, run_id: str = "starter-fixture") -> Path:
    bundle_path = run_data_dir(roots, run_id) / "normalized" / "course_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    built_at = _now()
    nodes: dict[str, dict[str, object]] = {}
    edges: list[dict[str, object]] = []
    source = bundle.get("source", {}) if isinstance(bundle.get("source"), dict) else {}
    source_id = str(source.get("source_id") or f"source:{run_id}")
    nodes[source_id] = _node(source_id, "source", source.get("title") or source_id, [str(source.get("source_ref") or "")])
    for course in bundle.get("courses", []):
        if not isinstance(course, dict):
            continue
        course_id = str(course["course_id"])
        nodes[course_id] = _node(course_id, "course", course.get("title"), [str(course.get("url") or "")])
        _edge(edges, "source_contains_course", source_id, course_id, course.get("url"), 1.0)
        progress = course.get("progress")
        if isinstance(progress, dict):
            progress_id = str(progress.get("progress_id") or f"{course_id}:progress")
            progress_label = " ".join(str(progress.get(key) or "") for key in ["state", "percent", "label"]).strip()
            nodes[progress_id] = _node(progress_id, "progress", progress_label or progress_id, [str(course.get("url") or "")])
            _edge(edges, "course_has_progress", course_id, progress_id, course.get("url"), 0.9)
        for module in course.get("modules", []):
            if not isinstance(module, dict):
                continue
            module_id = str(module["module_id"])
            nodes[module_id] = _node(module_id, "module", module.get("title"), [str(course.get("url") or "")])
            _edge(edges, "course_contains_module", course_id, module_id, course.get("url"), 1.0)
            for lesson in module.get("lessons", []):
                if not isinstance(lesson, dict):
                    continue
                lesson_id = str(lesson["lesson_id"])
                lesson_url = str(lesson.get("url") or "")
                lesson_freshness = str(lesson.get("freshness_state") or "unknown")
                lesson_temporal = _temporal_metadata(lesson, lesson.get("evidence"), indexed_at=built_at)
                nodes[lesson_id] = {
                    **_node(lesson_id, "lesson", lesson.get("title"), [lesson_url]),
                    "freshness_state": lesson_freshness,
                    **lesson_temporal,
                }
                version_group_id = str(lesson_temporal.get("version_group_id") or "")
                if version_group_id:
                    nodes.setdefault(version_group_id, _node(version_group_id, "version_group", lesson.get("title") or version_group_id, [lesson_url]))
                    _edge(edges, "version_group_has_snapshot", version_group_id, lesson_id, lesson_url, 1.0, lesson_temporal)
                lesson_confidence = 0.45 if lesson_freshness in {"discovered_not_fetched", "fetch_error", "access_denied"} else 1.0
                _edge(edges, "module_contains_lesson", module_id, lesson_id, lesson_url, lesson_confidence, lesson_temporal)
                for step in lesson.get("steps", []):
                    if isinstance(step, dict):
                        step_id = str(step["step_id"])
                        step_temporal = _temporal_metadata(step, step.get("evidence"), indexed_at=built_at, inherited=lesson_temporal)
                        nodes[step_id] = {
                            **_node(step_id, "step", str(step.get("text") or "")[:80], [lesson_url]),
                            "freshness_state": lesson_freshness,
                            "authority_tier": str(step.get("authority_tier") or ""),
                            "source_authority": str(step.get("source_authority") or ""),
                            **step_temporal,
                        }
                        step_version_group_id = str(step_temporal.get("version_group_id") or "")
                        if step_version_group_id:
                            nodes.setdefault(step_version_group_id, _node(step_version_group_id, "version_group", lesson.get("title") or step_version_group_id, [lesson_url]))
                            _edge(edges, "version_group_has_step_snapshot", step_version_group_id, step_id, lesson_url, 1.0, step_temporal)
                        step_confidence = 0.45 if lesson_freshness in {"discovered_not_fetched", "fetch_error", "access_denied"} else 1.0
                        _edge(edges, "lesson_contains_step", lesson_id, step_id, lesson_url, step_confidence, step_temporal)
                for asset in lesson.get("assets", []):
                    if isinstance(asset, dict):
                        asset_id = str(asset["asset_id"])
                        asset_temporal = _temporal_metadata(asset, asset.get("evidence"), indexed_at=built_at, inherited=lesson_temporal)
                        nodes[asset_id] = {**_node(asset_id, "asset", asset.get("title"), [str(asset.get("url") or lesson_url)]), **asset_temporal}
                        _edge(edges, "lesson_has_asset", lesson_id, asset_id, asset.get("url") or lesson_url, 0.9, asset_temporal)
                for transcript in lesson.get("transcripts", []):
                    if isinstance(transcript, dict):
                        transcript_id = str(transcript["transcript_id"])
                        transcript_temporal = _temporal_metadata(transcript, transcript.get("evidence"), indexed_at=built_at, inherited=lesson_temporal)
                        nodes[transcript_id] = {**_node(transcript_id, "transcript", transcript.get("language") or transcript_id, [lesson_url]), **transcript_temporal}
                        _edge(edges, "lesson_has_transcript", lesson_id, transcript_id, lesson_url, 0.9, transcript_temporal)
                for thread in lesson.get("comment_threads", []):
                    if isinstance(thread, dict):
                        thread_id = str(thread["thread_id"])
                        thread_temporal = _temporal_metadata(thread, thread.get("evidence"), indexed_at=built_at, inherited=lesson_temporal)
                        nodes[thread_id] = {**_node(thread_id, "comment_thread", thread.get("title") or thread_id, [lesson_url]), **thread_temporal}
                        _edge(edges, "lesson_has_comment_thread", lesson_id, thread_id, lesson_url, 0.8, thread_temporal)
                        for comment in thread.get("comments", []):
                            if isinstance(comment, dict):
                                comment_id = str(comment["comment_id"])
                                comment_temporal = _temporal_metadata(comment, comment.get("evidence"), indexed_at=built_at, inherited=thread_temporal)
                                nodes[comment_id] = {**_node(comment_id, "comment", str(comment.get("text") or "")[:80], [lesson_url]), **comment_temporal}
                                _edge(edges, "thread_has_comment", thread_id, comment_id, lesson_url, 0.8, comment_temporal)
                for topic in lesson.get("topics", []):
                    topic_id = f"topic:{str(topic).casefold()}"
                    nodes.setdefault(topic_id, _node(topic_id, "topic", topic, [lesson_url]))
                    _edge(edges, "lesson_about_topic", lesson_id, topic_id, lesson_url, 0.8, lesson_temporal)
                for entity in lesson.get("entities", []):
                    if isinstance(entity, dict):
                        entity_id = str(entity.get("entity_id"))
                        nodes.setdefault(entity_id, _node(entity_id, str(entity.get("kind") or "entity"), entity.get("value"), [lesson_url]))
                        _edge(edges, "lesson_mentions_entity", lesson_id, entity_id, lesson_url, 0.8, lesson_temporal)
                        for step in lesson.get("steps", []):
                            if isinstance(step, dict) and str(entity.get("value", "")).casefold() in str(step.get("text", "")).casefold():
                                _edge(edges, "step_mentions_entity", str(step["step_id"]), entity_id, lesson_url, 0.7, _temporal_metadata(step, step.get("evidence"), indexed_at=built_at, inherited=lesson_temporal))
    output_dir = run_artifact_dir(roots, run_id) / "graphs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "course_graph.json"
    payload = {
        "schema": "aoa_course_graph_v1",
        "run_id": run_id,
        "built_at": built_at,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "temporal": _temporal_summary(list(nodes.values()), edges),
        "nodes": list(nodes.values()),
        "edges": edges,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _node(node_id: str, kind: str, label: object, source_refs: list[str]) -> dict[str, object]:
    return {"schema": "aoa_course_graph_node_v1", "node_id": node_id, "kind": kind, "label": str(label or node_id), "source_refs": source_refs}


def _edge(
    edges: list[dict[str, object]],
    kind: str,
    from_node: str,
    to_node: str,
    source_ref: object,
    confidence: float,
    temporal: dict[str, object] | None = None,
) -> None:
    edge_id = f"{from_node}->{to_node}:{kind}"
    if any(edge.get("edge_id") == edge_id for edge in edges):
        return
    temporal = temporal or {}
    edges.append(
        {
            "schema": "aoa_course_graph_edge_v1",
            "edge_id": edge_id,
            "kind": kind,
            "from_node": from_node,
            "to_node": to_node,
            "source_refs": [str(source_ref or "")],
            "confidence": confidence,
            **_edge_temporal(temporal),
        }
    )


def _temporal_metadata(
    item: dict[str, object],
    evidence: object,
    *,
    indexed_at: str,
    inherited: dict[str, object] | None = None,
) -> dict[str, object]:
    inherited = inherited or {}
    evidence_dict = evidence if isinstance(evidence, dict) else {}
    metadata: dict[str, object] = {}
    for key in ["version_group_id", "valid_from", "valid_until"]:
        value = item.get(key) or inherited.get(key)
        if value:
            metadata[key] = value
    observed_at = item.get("observed_at") or inherited.get("observed_at") or evidence_dict.get("fetched_at")
    if observed_at:
        metadata["observed_at"] = observed_at
    if metadata:
        metadata["indexed_at"] = indexed_at
        metadata["temporal_state"] = _temporal_state(metadata)
    return metadata


def _edge_temporal(temporal: dict[str, object]) -> dict[str, object]:
    return {
        key: temporal[key]
        for key in ["version_group_id", "valid_from", "valid_until", "observed_at", "indexed_at", "temporal_state"]
        if temporal.get(key)
    }


def _temporal_state(metadata: dict[str, object]) -> str:
    if metadata.get("valid_from") and metadata.get("valid_until"):
        return "bounded"
    if metadata.get("valid_from"):
        return "open_current"
    if metadata.get("observed_at"):
        return "observed"
    return "unknown"


def _temporal_summary(nodes: list[dict[str, object]], edges: list[dict[str, object]]) -> dict[str, object]:
    versioned_nodes = [node for node in nodes if node.get("version_group_id")]
    timestamped_edges = [edge for edge in edges if edge.get("valid_from") or edge.get("valid_until") or edge.get("observed_at")]
    observed = sorted(str(node.get("observed_at")) for node in nodes if node.get("observed_at"))
    return {
        "schema": "aoa_course_graph_temporal_summary_v1",
        "version_group_count": len({str(node.get("version_group_id")) for node in versioned_nodes}),
        "snapshot_node_count": len(versioned_nodes),
        "timestamped_edge_count": len(timestamped_edges),
        "observed_at_min": observed[0] if observed else "",
        "observed_at_max": observed[-1] if observed else "",
    }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
