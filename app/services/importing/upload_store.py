import uuid
from pathlib import Path

from app.config import get_settings


def _upload_dir() -> Path:
    path = Path(get_settings().upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_upload(content: bytes, filename: str) -> str:
    upload_id = uuid.uuid4().hex
    target = _upload_dir() / f"{upload_id}__{filename}"
    target.write_bytes(content)
    return upload_id


def find_upload(upload_id: str) -> Path:
    matches = list(_upload_dir().glob(f"{upload_id}__*"))
    if not matches:
        raise FileNotFoundError(f"No se encuentra el fichero temporal {upload_id}")
    return matches[0]


def load_upload(upload_id: str) -> tuple[bytes, str]:
    path = find_upload(upload_id)
    filename = path.name.split("__", 1)[1]
    return path.read_bytes(), filename


def delete_upload(upload_id: str) -> None:
    try:
        find_upload(upload_id).unlink(missing_ok=True)
    except FileNotFoundError:
        pass
