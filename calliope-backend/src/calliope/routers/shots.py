"""Build Scene — shot composition + capture storage.

One composition per agent session (get-or-create, keyed by the UNIQUE
agent_session_id). `scene_json` is the single source of truth for the 3D
blockout (objects, transforms, posture v7, shot params); the frontend and the
agent's shot_builder tools both mutate it through this router. Captures are
PNG renders posted as data URLs and saved under <assets_dir>/shots/ (served by
/api/file and rebased on folder moves like every other asset path).
"""
from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from calliope.config import settings
from calliope.db import get_db, row_to_dict
from calliope.events.bus import event_bus

router = APIRouter()

OBJECT_TYPES = {
    "male",
    "female",
    "child",
    "cube",
    "plane",
    "cylinder",
    "sphere",
    "capsule",
    "cone",
    "torus",
    "camera",
}

_MAX_SCENE_JSON_CHARS = 4_000_000
_MAX_IMAGE_BYTES = 20_000_000
_MAX_VIDEO_BYTES = 64_000_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ShotCreate(BaseModel):
    agent_session_id: int | None = None
    title: str | None = None
    scene_json: str | None = None

    @field_validator("title")
    @classmethod
    def _bound_title(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 300:
            raise ValueError("Title too long (max 300 characters)")
        return v


class ShotPatch(BaseModel):
    title: str | None = None
    scene_json: str | None = None
    capture_request_json: str | None = None

    @field_validator("title")
    @classmethod
    def _bound_title(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 300:
            raise ValueError("Title too long (max 300 characters)")
        return v


class CaptureCreate(BaseModel):
    data_url: str
    label: str | None = None
    meta_json: str | None = None

    @field_validator("label")
    @classmethod
    def _bound_label(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 200:
            raise ValueError("Label too long (max 200 characters)")
        return v


def validate_scene_json(raw: str) -> dict[str, Any]:
    """Light structural validation — the client owns deep validation (posture
    shapes, value ranges) via the ported posture module."""
    if len(raw) > _MAX_SCENE_JSON_CHARS:
        raise HTTPException(status_code=413, detail="scene_json too large")
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"scene_json is not valid JSON: {exc}")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="scene_json must be a JSON object")
    objects = data.get("objects", [])
    if not isinstance(objects, list):
        raise HTTPException(status_code=422, detail="scene_json.objects must be a list")
    for idx, obj in enumerate(objects):
        if not isinstance(obj, dict):
            raise HTTPException(status_code=422, detail=f"objects[{idx}] must be an object")
        if not obj.get("id") or not isinstance(obj.get("id"), str):
            raise HTTPException(status_code=422, detail=f"objects[{idx}].id must be a string")
        if obj.get("type") not in OBJECT_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"objects[{idx}].type '{obj.get('type')}' is not a known object type",
            )
    return data


def _composition_out(row: Any, *, include_scene: bool = False) -> dict[str, Any]:
    out = {
        "id": row["id"],
        "agent_session_id": row["agent_session_id"],
        "title": row["title"],
        "capture_request_json": row["capture_request_json"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_scene:
        try:
            out["scene"] = json.loads(row["scene_json"] or "{}")
        except json.JSONDecodeError:
            out["scene"] = {}
    else:
        out["has_scene"] = bool(row["scene_json"] and row["scene_json"] != "{}")
    return out


def _capture_out(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "composition_id": row["composition_id"],
        "kind": row["kind"],
        "label": row["label"],
        "file_path": row["file_path"],
        "created_at": row["created_at"],
    }


def get_or_create_for_session(
    conn: Any, session_id: int, *, title: str | None = None
) -> dict[str, Any]:
    """Shared with the shot_builder plugin: one composition per session."""
    row = conn.execute(
        "SELECT * FROM shot_composition WHERE agent_session_id = ?",
        (session_id,),
    ).fetchone()
    if row:
        return row_to_dict(row)
    effective_title = (title or "").strip() or "Untitled composition"
    cur = conn.execute(
        """
        INSERT INTO shot_composition (agent_session_id, title, scene_json, created_at, updated_at)
        VALUES (?, ?, '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (session_id, effective_title[:300]),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM shot_composition WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return row_to_dict(row)


@router.get("")
async def list_shots() -> list[dict[str, Any]]:
    conn = get_db(settings.db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM shot_composition ORDER BY updated_at DESC, id DESC"
        ).fetchall()
        return [_composition_out(r) for r in rows]
    finally:
        conn.close()


@router.post("")
async def create_shot(payload: ShotCreate) -> dict[str, Any]:
    conn = get_db(settings.db_path)
    try:
        if payload.agent_session_id is not None:
            if not conn.execute(
                "SELECT id FROM agent_sessions WHERE id = ?", (payload.agent_session_id,)
            ).fetchone():
                raise HTTPException(status_code=404, detail="Agent session not found")
            row = get_or_create_for_session(
                conn, payload.agent_session_id, title=payload.title
            )
            created = row["created_at"] == row["updated_at"]
        else:
            title = (payload.title or "").strip() or "Untitled composition"
            scene = "{}"
            if payload.scene_json is not None:
                validate_scene_json(payload.scene_json)
                scene = payload.scene_json
            cur = conn.execute(
                """
                INSERT INTO shot_composition (agent_session_id, title, scene_json, created_at, updated_at)
                VALUES (NULL, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (title[:300], scene),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM shot_composition WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            created = True
        out = _composition_out(row, include_scene=True)
        out["created"] = created
    finally:
        conn.close()
    await event_bus.publish(
        "shot.updated",
        {"shot_id": out["id"], "reason": "created"},
    )
    return out


@router.get("/by-session/{session_id}")
async def get_or_create_by_session(session_id: int) -> dict[str, Any]:
    conn = get_db(settings.db_path)
    try:
        if not conn.execute(
            "SELECT id FROM agent_sessions WHERE id = ?", (session_id,)
        ).fetchone():
            raise HTTPException(status_code=404, detail="Agent session not found")
        row = get_or_create_for_session(conn, session_id)
        out = _composition_out(row, include_scene=True)
        out["created"] = row["created_at"] == row["updated_at"] and not row["scene_json"]
    finally:
        conn.close()
    if out.pop("created", False):
        await event_bus.publish("shot.updated", {"shot_id": out["id"], "reason": "created"})
    return out


@router.get("/{shot_id}")
async def get_shot(shot_id: int) -> dict[str, Any]:
    conn = get_db(settings.db_path)
    try:
        row = conn.execute(
            "SELECT * FROM shot_composition WHERE id = ?", (shot_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Composition not found")
        return _composition_out(row, include_scene=True)
    finally:
        conn.close()


@router.patch("/{shot_id}")
async def patch_shot(shot_id: int, payload: ShotPatch) -> dict[str, Any]:
    conn = get_db(settings.db_path)
    try:
        row = conn.execute(
            "SELECT * FROM shot_composition WHERE id = ?", (shot_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Composition not found")
        sets: list[str] = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = []
        if payload.title is not None:
            sets.append("title = ?")
            params.append(payload.title.strip()[:300] or "Untitled composition")
        if payload.scene_json is not None:
            validate_scene_json(payload.scene_json)
            sets.append("scene_json = ?")
            params.append(payload.scene_json)
        if payload.capture_request_json is not None:
            if payload.capture_request_json == "":
                sets.append("capture_request_json = NULL")
            else:
                try:
                    json.loads(payload.capture_request_json)
                except json.JSONDecodeError as exc:
                    raise HTTPException(
                        status_code=422, detail=f"capture_request_json invalid: {exc}"
                    )
                sets.append("capture_request_json = ?")
                params.append(payload.capture_request_json)
        params.append(shot_id)
        conn.execute(
            f"UPDATE shot_composition SET {', '.join(sets)} WHERE id = ?", params
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM shot_composition WHERE id = ?", (shot_id,)
        ).fetchone()
        out = _composition_out(row, include_scene=True)
    finally:
        conn.close()
    await event_bus.publish(
        "shot.updated",
        {"shot_id": shot_id, "reason": "patched"},
    )
    return out


@router.delete("/{shot_id}")
async def delete_shot(shot_id: int) -> dict[str, bool]:
    conn = get_db(settings.db_path)
    try:
        if not conn.execute(
            "SELECT id FROM shot_composition WHERE id = ?", (shot_id,)
        ).fetchone():
            raise HTTPException(status_code=404, detail="Composition not found")
        conn.execute("DELETE FROM shot_composition WHERE id = ?", (shot_id,))
        conn.commit()
    finally:
        conn.close()
    await event_bus.publish("shot.updated", {"shot_id": shot_id, "reason": "deleted"})
    return {"ok": True}


# ---- captures --------------------------------------------------------------


@router.get("/{shot_id}/captures")
async def list_captures(shot_id: int) -> list[dict[str, Any]]:
    conn = get_db(settings.db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM shot_capture WHERE composition_id = ? ORDER BY id DESC",
            (shot_id,),
        ).fetchall()
        return [_capture_out(r) for r in rows]
    finally:
        conn.close()


def _decode_data_url(data_url: str) -> tuple[bytes, str, str]:
    """Returns (raw bytes, extension, capture kind)."""
    if not data_url.startswith("data:"):
        raise HTTPException(status_code=422, detail="data_url must be an image or video data URL")
    header, _, b64 = data_url.partition(",")
    if not b64:
        raise HTTPException(status_code=422, detail="data_url missing base64 payload")
    mime = header[len("data:") :].split(";", 1)[0].strip().lower()
    if mime.startswith("image/"):
        kind = "image"
        ext = "png"
        marker = mime[len("image/") :]
        if marker in {"png", "jpeg", "jpg", "webp", "gif"}:
            ext = "jpeg" if marker == "jpg" else marker
        max_bytes = _MAX_IMAGE_BYTES
    elif mime.startswith("video/"):
        kind = "video"
        marker = mime[len("video/") :]
        ext = {"mp4": "mp4", "webm": "webm", "quicktime": "mov"}.get(marker, "mp4")
        max_bytes = _MAX_VIDEO_BYTES
    else:
        raise HTTPException(
            status_code=422, detail="data_url must be an image/* or video/* data URL"
        )
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="data_url payload is not valid base64")
    if not raw or len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"capture must be 1 byte..{max_bytes} bytes",
        )
    return raw, ext, kind


@router.post("/{shot_id}/captures")
async def create_capture(shot_id: int, payload: CaptureCreate) -> dict[str, Any]:
    raw, ext, kind = _decode_data_url(payload.data_url)
    conn = get_db(settings.db_path)
    try:
        if not conn.execute(
            "SELECT id FROM shot_composition WHERE id = ?", (shot_id,)
        ).fetchone():
            raise HTTPException(status_code=404, detail="Composition not found")
        shots_dir = settings.assets_dir / "shots" / str(shot_id)
        shots_dir.mkdir(parents=True, exist_ok=True)
        file_path = shots_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"
        file_path.write_bytes(raw)
        cur = conn.execute(
            """
            INSERT INTO shot_capture (composition_id, kind, label, file_path, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (shot_id, kind, payload.label, str(file_path), payload.meta_json),
        )
        # The capture request has been fulfilled — clear it so the next
        # request_capture polls for a fresh one.
        conn.execute(
            "UPDATE shot_composition SET capture_request_json = NULL, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (shot_id,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM shot_capture WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        out = _capture_out(row)
    finally:
        conn.close()
    await event_bus.publish(
        "shot.capture.saved",
        {
            "shot_id": shot_id,
            "capture_id": out["id"],
            "file_path": out["file_path"],
            "label": out["label"],
        },
    )
    return out


@router.delete("/{shot_id}/captures/{capture_id}")
async def delete_capture(shot_id: int, capture_id: int) -> dict[str, bool]:
    conn = get_db(settings.db_path)
    try:
        row = conn.execute(
            "SELECT id, file_path FROM shot_capture WHERE id = ? AND composition_id = ?",
            (capture_id, shot_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Capture not found")
        conn.execute("DELETE FROM shot_capture WHERE id = ?", (capture_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
