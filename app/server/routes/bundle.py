"""
Bundle-source viewer.

Serves a read-only snapshot of the Databricks Asset Bundle (databricks.yml,
README, src/, and app/) so a customer can browse exactly how the
pipeline and Lakebase instance are deployed. Auth is OBO (Databricks Apps
front-door SSO), matching the other admin routes.

The snapshot itself is built by `scripts/snapshot_bundle.sh` before
`databricks bundle deploy`. Re-run that script whenever bundle code changes.
"""
from __future__ import annotations
import io
import os
import zipfile
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from ..auth import require_obo

router = APIRouter(prefix="/v1/admin/bundle", tags=["bundle"])

BUNDLE_ROOT = (Path(__file__).resolve().parent.parent / "_bundle_source").resolve()
EXCLUDED_DIRS = {"__pycache__", ".git", "node_modules", ".pytest_cache"}
EXCLUDED_FILES = {".DS_Store"}
MAX_VIEW_BYTES = 2 * 1024 * 1024  # 2 MB cap on file viewing


def _safe(rel: str) -> Path:
    """Resolve a relative path inside BUNDLE_ROOT, refusing any traversal."""
    if rel is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing path")
    rel = rel.lstrip("/")
    candidate = (BUNDLE_ROOT / rel).resolve()
    try:
        candidate.relative_to(BUNDLE_ROOT)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "path escapes bundle root")
    return candidate


def _display_path(rel_str: str) -> str:
    """Snapshot script renames *.py → *.py.txt so Databricks Apps source upload
    doesn't classify them as Notebook objects (which would strip .py). For the
    viewer, hide that trick: show the path as *.py."""
    return rel_str[:-4] if rel_str.endswith(".py.txt") else rel_str


def _display_name(name: str) -> str:
    return name[:-4] if name.endswith(".py.txt") else name


def _display_ext(p: Path) -> str:
    s = p.name
    if s.endswith(".py.txt"):
        return ".py"
    return p.suffix.lower()


def _file_meta(p: Path) -> dict:
    rel = str(p.relative_to(BUNDLE_ROOT)).replace(os.sep, "/")
    return {
        "path": _display_path(rel),
        "name": _display_name(p.name),
        "size": p.stat().st_size if p.is_file() else None,
        "type": "dir" if p.is_dir() else "file",
        "ext": _display_ext(p),
    }


def _resolve_disk_path(req_path: str) -> Path:
    """Map a user-facing path (e.g. src/deploy/setup_lakebase.py) to the on-disk
    file, which may have a .txt suffix appended by the snapshot script."""
    p = _safe(req_path)
    if p.exists():
        return p
    # Try with the snapshot's .py.txt suffix
    if req_path.endswith(".py"):
        p2 = _safe(req_path + ".txt")
        if p2.exists():
            return p2
    return p  # let the caller handle the not-found case


def _walk_filtered():
    for root, dirs, files in os.walk(BUNDLE_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for d in dirs:
            yield Path(root) / d
        for f in files:
            if f in EXCLUDED_FILES or f.endswith(".pyc"):
                continue
            yield Path(root) / f


@router.get("/files")
def list_files(_=Depends(require_obo)):
    if not BUNDLE_ROOT.exists():
        return {
            "root": str(BUNDLE_ROOT),
            "items": [],
            "error": "bundle source not snapshotted. Run scripts/snapshot_bundle.sh and redeploy.",
        }
    items = [_file_meta(p) for p in _walk_filtered()]
    items.sort(key=lambda i: (0 if i["type"] == "dir" else 1, i["path"].lower()))
    return {
        "root": "bundle",
        "default_path": "README.md",
        "items": items,
    }


_LANG_BY_EXT = {
    ".py": "python", ".sql": "sql", ".js": "javascript", ".ts": "typescript",
    ".css": "css", ".html": "html", ".json": "json", ".yml": "yaml",
    ".yaml": "yaml", ".sh": "bash", ".md": "markdown", ".markdown": "markdown",
    ".txt": "text", ".toml": "toml",
}


@router.get("/content")
def get_content(path: str = Query(...), _=Depends(require_obo)):
    p = _resolve_disk_path(path)
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"not found: {path}")
    if not p.is_file():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "path is a directory, not a file")
    size = p.stat().st_size
    if size > MAX_VIEW_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"file too large to view ({size} bytes > {MAX_VIEW_BYTES})")
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "binary file (cannot display)")
    rel = str(p.relative_to(BUNDLE_ROOT)).replace(os.sep, "/")
    ext = _display_ext(p)
    out = {
        "path": _display_path(rel),
        "name": _display_name(p.name),
        "ext": ext,
        "size": size,
        "language": _LANG_BY_EXT.get(ext, "text"),
        "text": text,
    }
    if ext in (".md", ".markdown"):
        try:
            import markdown as _md
            out["html"] = _md.markdown(
                text,
                extensions=["fenced_code", "tables", "toc", "sane_lists"],
                output_format="html5",
            )
        except Exception as e:
            out["html_error"] = str(e)
    return out


@router.get("/download")
def download_zip(_=Depends(require_obo)):
    if not BUNDLE_ROOT.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bundle source not snapshotted")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in _walk_filtered():
            if p.is_file():
                rel = str(p.relative_to(BUNDLE_ROOT)).replace(os.sep, "/")
                arcname = "traackr-influencer-bundle/" + _display_path(rel)
                z.write(p, arcname=arcname)
    buf.seek(0)
    data = buf.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="traackr-influencer-bundle.zip"',
            "Content-Length": str(len(data)),
        },
    )
