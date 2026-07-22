"""Private local object storage with content validation and atomic writes."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import secrets
import tempfile


ALLOWED_MIME = {
    "image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp",
    "audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/wav": "wav", "audio/mp4": "m4a",
    "video/mp4": "mp4", "application/pdf": "pdf", "application/zip": "zip", "text/plain": "txt",
}


def detect_mime(data: bytes) -> str:
    if data.startswith((b"MZ",b"\x7fELF")): return "application/x-executable"
    if data.startswith(b"\xff\xd8\xff"): return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")): return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP": return "image/webp"
    if data.startswith(b"OggS"): return "audio/ogg"
    if data.startswith(b"ID3") or (len(data) > 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0): return "audio/mpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE": return "audio/wav"
    if data.startswith(b"%PDF-"): return "application/pdf"
    if data.startswith(b"PK\x03\x04"): return "application/zip"
    if len(data) > 12 and data[4:8] == b"ftyp":
        return "audio/mp4" if data[8:12] in {b"M4A ", b"M4B "} else "video/mp4"
    if data and b"\x00" not in data[:4096]:
        try: data[:4096].decode("utf-8"); return "text/plain"
        except UnicodeDecodeError: pass
    return "application/octet-stream"


@dataclass(frozen=True)
class StoredObject:
    key: str
    safe_filename: str
    detected_mime: str
    size: int
    sha256: str


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.objects = self.root / "objects"
        self.temp = self.root / "tmp"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.temp.mkdir(parents=True, exist_ok=True)

    def store(self, data: bytes, *, max_bytes: int, allowed_mime: set[str] | None = None) -> StoredObject:
        if not data: raise ValueError("empty file")
        if len(data) > max_bytes: raise ValueError("file too large")
        mime = detect_mime(data)
        allowed = allowed_mime or set(ALLOWED_MIME)
        if mime not in allowed: raise ValueError("file type not allowed")
        digest = hashlib.sha256(data).hexdigest()
        ext = ALLOWED_MIME[mime]
        safe = f"{secrets.token_hex(16)}.{ext}"
        key = f"{digest[:2]}/{safe}"
        target = (self.objects / key).resolve()
        if self.objects not in target.parents: raise ValueError("invalid storage key")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self.temp)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data); handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name): os.unlink(tmp_name)
        return StoredObject(key, safe, mime, len(data), digest)

    def read(self, key: str) -> bytes:
        path = (self.objects / key).resolve()
        if self.objects not in path.parents: raise ValueError("invalid storage key")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path=(self.objects/key).resolve()
        if self.objects not in path.parents: raise ValueError("invalid storage key")
        if path.exists(): path.unlink()

    def cleanup_temp(self) -> int:
        removed = 0
        for path in self.temp.iterdir():
            if path.is_file(): path.unlink(); removed += 1
        return removed
