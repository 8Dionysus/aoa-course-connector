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
                nodes[lesson_id] = _node(lesson_id, "lesson", lesson.get("title"), [lesson_url])
                _edge(edges, "module_contains_lesson", module_id, lesson_id, lesson_url, 1.0)
                for step in lesson.get("steps", []):
                    if isinstance(step, dict):
                        step_id = str(step["step_id"])
                        nodes[step_id] = _node(step_id, "step", str(step.get("text") or "")[:80], [lesson_url])
                        _edge(edges, "lesson_contains_step", lesson_id, step_id, lesson_url, 1.0)
                for asset in lesson.get("assets", []):
                    if isinstance(asset, dict):
                        asset_id = str(asset["asset_id"])
                        nodes[asset_id] = _node(asset_id, "asset", asset.get("title"), [str(asset.get("url") or lesson_url)])
                        _edge(edges, "lesson_has_asset", lesson_id, asset_id, asset.get("url") or lesson_url, 0.9)
                for transcript in lesson.get("transcripts", []):
                    if isinstance(transcript, dict):
                        transcript_id = str(transcript["transcript_id"])
                        nodes[transcript_id] = _node(transcript_id, "transcript", transcript.get("language") or transcript_id, [lesson_url])
                        _edge(edges, "lesson_has_transcript", lesson_id, transcript_id, lesson_url, 0.9)
                for topic in lesson.get("topics", []):
                    topic_id = f"topic:{str(topic).casefold()}"
                    nodes.setdefault(topic_id, _node(topic_id, "topic", topic, [lesson_url]))
                    _edge(edges, "lesson_about_topic", lesson_id, topic_id, lesson_url, 0.8)
                for entity in lesson.get("entities", []):
                    if isinstance(entity, dict):
                        entity_id = str(entity.get("entity_id"))
                        nodes.setdefault(entity_id, _node(entity_id, str(entity.get("kind") or "entity"), entity.get("value"), [lesson_url]))
                        _edge(edges, "lesson_mentions_entity", lesson_id, entity_id, lesson_url, 0.8)
                        for step in lesson.get("steps", []):
                            if isinstance(step, dict) and str(entity.get("value", "")).casefold() in str(step.get("text", "")).casefold():
                                _edge(edges, "step_mentions_entity", str(step["step_id"]), entity_id, lesson_url, 0.7)
    output_dir = run_artifact_dir(roots, run_id) / "graphs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "course_graph.json"
    payload = {
        "schema": "aoa_course_graph_v1",
        "run_id": run_id,
        "built_at": _now(),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": list(nodes.values()),
        "edges": edges,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _node(node_id: str, kind: str, label: object, source_refs: list[str]) -> dict[str, object]:
    return {"schema": "aoa_course_graph_node_v1", "node_id": node_id, "kind": kind, "label": str(label or node_id), "source_refs": source_refs}


def _edge(edges: list[dict[str, object]], kind: str, from_node: str, to_node: str, source_ref: object, confidence: float) -> None:
    edge_id = f"{from_node}->{to_node}:{kind}"
    if any(edge.get("edge_id") == edge_id for edge in edges):
        return
    edges.append(
        {
            "schema": "aoa_course_graph_edge_v1",
            "edge_id": edge_id,
            "kind": kind,
            "from_node": from_node,
            "to_node": to_node,
            "source_refs": [str(source_ref or "")],
            "confidence": confidence,
        }
    )


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
