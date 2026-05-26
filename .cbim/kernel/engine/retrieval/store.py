"""IndexStore — on-disk layout per contract.md §Index Storage Paths.

Layout (frozen public contract):
    .cbim/index/
      config.json
      <source>/
        meta.json       # {doc_id: {mtime, size, sha256, indexed_at, metadata, source_path?}}
        vectors.bin     # binary [N, dim] float32 (provider available only)
        bm25.json       # inverted index + doc-length table
        docs/<doc_id>.txt  # full text snapshot

doc_id sanitization: doc_ids may contain path separators / slashes, so we
percent-encode unsafe chars to make them filesystem-safe. The original
doc_id is the lookup key in meta.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


VALID_SOURCES = ("transcript", "memory_medium", "dna", "agents")


class StoreError(Exception):
    pass


_SAFE = re.compile(r"[A-Za-z0-9._-]")


def _safe_doc_filename(doc_id: str) -> str:
    """Percent-encode characters not in [A-Za-z0-9._-]. Pure ASCII output.

    Reversible: e.g. 'a/b c' -> 'a%2Fb%20c'. Used for both docs/*.txt and
    in meta.json the original doc_id is preserved as the lookup key.
    """
    out = []
    for ch in doc_id:
        if _SAFE.match(ch):
            out.append(ch)
        else:
            for b in ch.encode("utf-8"):
                out.append(f"%{b:02X}")
    name = "".join(out)
    # Avoid empty / dot-only names
    if not name or name in (".", ".."):
        name = "_" + name
    return name


@dataclass
class DocRecord:
    doc_id: str
    mtime: float
    size: int
    sha256: str
    indexed_at: str
    metadata: dict = field(default_factory=dict)
    source_path: Optional[str] = None  # absolute path of original file (when known)

    def to_dict(self) -> dict:
        return {
            "mtime": self.mtime,
            "size": self.size,
            "sha256": self.sha256,
            "indexed_at": self.indexed_at,
            "metadata": self.metadata,
            "source_path": self.source_path,
        }

    @classmethod
    def from_dict(cls, doc_id: str, data: dict) -> "DocRecord":
        return cls(
            doc_id=doc_id,
            mtime=float(data.get("mtime", 0.0)),
            size=int(data.get("size", 0)),
            sha256=str(data.get("sha256", "")),
            indexed_at=str(data.get("indexed_at", "")),
            metadata=dict(data.get("metadata") or {}),
            source_path=data.get("source_path"),
        )


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


class IndexStore:
    """Per-source on-disk store. Single source = single directory."""

    def __init__(self, index_root: Path, source: str) -> None:
        if source not in VALID_SOURCES:
            raise StoreError(f"unknown source: {source!r}")
        self.index_root = index_root
        self.source = source
        self.source_dir = index_root / source
        self.docs_dir = self.source_dir / "docs"
        self.meta_path = self.source_dir / "meta.json"
        self.bm25_path = self.source_dir / "bm25.json"
        self.vectors_path = self.source_dir / "vectors.bin"

    # ---------------- meta.json ----------------

    def load_meta(self) -> Dict[str, DocRecord]:
        if not self.meta_path.exists():
            return {}
        try:
            raw = json.loads(self.meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        out: Dict[str, DocRecord] = {}
        for doc_id, rec in (raw.get("docs") or {}).items():
            out[doc_id] = DocRecord.from_dict(doc_id, rec)
        return out

    def save_meta(self, records: Dict[str, DocRecord]) -> None:
        self.source_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "source": self.source,
            "docs": {doc_id: rec.to_dict() for doc_id, rec in records.items()},
        }
        _atomic_write_json(self.meta_path, payload)

    # ---------------- docs/<doc_id>.txt ----------------

    def doc_path(self, doc_id: str) -> Path:
        return self.docs_dir / (_safe_doc_filename(doc_id) + ".txt")

    def write_doc(self, doc_id: str, content: str) -> None:
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        path = self.doc_path(doc_id)
        tmp = path.with_suffix(".txt.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)

    def read_doc(self, doc_id: str) -> Optional[str]:
        path = self.doc_path(doc_id)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def delete_doc(self, doc_id: str) -> None:
        path = self.doc_path(doc_id)
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass

    # ---------------- bm25.json ----------------

    def load_bm25_state(self) -> Optional[dict]:
        if not self.bm25_path.exists():
            return None
        try:
            return json.loads(self.bm25_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def save_bm25_state(self, state: dict) -> None:
        self.source_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.bm25_path, state)

    # ---------------- vectors.bin ----------------

    def load_vectors(self) -> Optional["VectorBlob"]:
        if not self.vectors_path.exists():
            return None
        try:
            return VectorBlob.load(self.vectors_path)
        except (OSError, ValueError):
            return None

    def save_vectors(self, blob: "VectorBlob") -> None:
        self.source_dir.mkdir(parents=True, exist_ok=True)
        blob.save(self.vectors_path)

    # ---------------- diagnostics ----------------

    def total_size_bytes(self) -> int:
        if not self.source_dir.exists():
            return 0
        total = 0
        for p in self.source_dir.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        return total


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# VectorBlob — minimal float32 [N, dim] container, pure stdlib.
# --------------------------------------------------------------------------
#
# Format (little-endian):
#   magic        : 4 bytes b"CBIV"
#   version      : uint32
#   dim          : uint32
#   count        : uint32
#   id_table_len : uint32  (length in bytes of UTF-8 JSON array of doc_ids)
#   id_table     : UTF-8 JSON array of doc_ids (length = count)
#   vectors      : float32 * count * dim
#
# numpy is optional; if absent we use array.array("f", ...).
# --------------------------------------------------------------------------

import struct
from typing import List


class VectorBlob:
    MAGIC = b"CBIV"
    VERSION = 1

    def __init__(self, dim: int) -> None:
        self.dim = int(dim)
        self.doc_ids: List[str] = []
        self.vectors: List[List[float]] = []

    def upsert(self, doc_id: str, vec: list) -> None:
        if len(vec) != self.dim:
            raise StoreError(f"vector dim mismatch: expected {self.dim}, got {len(vec)}")
        vec = [float(x) for x in vec]
        if doc_id in self.doc_ids:
            idx = self.doc_ids.index(doc_id)
            self.vectors[idx] = vec
        else:
            self.doc_ids.append(doc_id)
            self.vectors.append(vec)

    def delete(self, doc_id: str) -> None:
        if doc_id in self.doc_ids:
            idx = self.doc_ids.index(doc_id)
            del self.doc_ids[idx]
            del self.vectors[idx]

    def get(self, doc_id: str) -> Optional[List[float]]:
        if doc_id in self.doc_ids:
            return self.vectors[self.doc_ids.index(doc_id)]
        return None

    def save(self, path: Path) -> None:
        import array
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        id_blob = json.dumps(self.doc_ids, ensure_ascii=False).encode("utf-8")
        header = struct.pack(
            "<4sIIII",
            self.MAGIC,
            self.VERSION,
            self.dim,
            len(self.doc_ids),
            len(id_blob),
        )
        flat = array.array("f")
        for v in self.vectors:
            flat.extend(v)
        with open(tmp, "wb") as f:
            f.write(header)
            f.write(id_blob)
            flat.tofile(f)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: Path) -> "VectorBlob":
        import array
        with open(path, "rb") as f:
            header = f.read(struct.calcsize("<4sIIII"))
            if len(header) < struct.calcsize("<4sIIII"):
                raise ValueError("truncated vectors.bin header")
            magic, version, dim, count, id_len = struct.unpack("<4sIIII", header)
            if magic != cls.MAGIC:
                raise ValueError(f"bad magic: {magic!r}")
            if version != cls.VERSION:
                raise ValueError(f"unsupported version: {version}")
            id_blob = f.read(id_len)
            if len(id_blob) < id_len:
                raise ValueError("truncated id table")
            doc_ids = json.loads(id_blob.decode("utf-8"))
            if len(doc_ids) != count:
                raise ValueError("id table count mismatch")
            flat = array.array("f")
            flat.fromfile(f, count * dim)
        blob = cls(dim)
        blob.doc_ids = list(doc_ids)
        for i in range(count):
            blob.vectors.append(list(flat[i * dim : (i + 1) * dim]))
        return blob
