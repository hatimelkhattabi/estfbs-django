import mimetypes
import re
import uuid
from pathlib import Path
from urllib.parse import unquote, quote
from PIL import Image
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header
from .validators import valid_link


def asset_url(path):
    if not path:
        return ""
    if str(path).startswith(("http://", "https://")):
        return str(path) if valid_link(str(path)) else ""
    return settings.STATIC_URL + str(path).lstrip("/")


def is_private(path):
    return (
        str(path or "")
        .lstrip("/")
        .startswith(
            (
                "uploads/",
                "documents/",
                "publications/",
                "professeurs/",
                "gallery/",
                "galerie/",
                "reglements/",
                "medias/",
                "covers/",
            )
        )
    )


def private_storage():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def checked_file(upload, kind="document", max_mb=None):
    max_mb = max_mb or (100 if kind == "video" else (5 if kind == "image" else 20))
    if upload.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Le fichier doit peser au maximum {max_mb} Mo.")
    ext = Path(upload.name).suffix.lower()
    head = upload.read(64)
    upload.seek(0)
    if kind == "video":
        good = (ext == ".mp4" and b"ftyp" in head[:32]) or (
            ext == ".webm" and head.startswith(b"\x1a\x45\xdf\xa3")
        )
        if not good:
            raise ValidationError("Choisissez une vidéo MP4 ou WebM valide.")
        return "video/mp4" if ext == ".mp4" else "video/webm"
    if ext == ".pdf" and head.startswith(b"%PDF-") and kind != "image":
        return "application/pdf"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise ValidationError(
            "Choisissez un PDF ou une image JPG, PNG ou WebP."
            if kind != "image"
            else "Choisissez une image JPG, PNG ou WebP."
        )
    try:
        with Image.open(upload) as image:
            fmt = image.format
            image.verify()
        upload.seek(0)
    except Exception as exc:
        raise ValidationError("L’image est invalide.") from exc
    allowed = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
    if fmt != allowed[ext]:
        raise ValidationError(
            "Le type réel du fichier ne correspond pas à son extension."
        )
    return Image.MIME[fmt]


def save_upload(upload, folder, kind="document", max_mb=None):
    mime = checked_file(upload, kind, max_mb)
    name = f"{folder}/{uuid.uuid4().hex}{Path(upload.name).suffix.lower()}"
    return private_storage().save(name, upload), mime


def save_document(upload, user=None):
    from .models import UploadedDocument

    path, mime = save_upload(upload, "documents")
    try:
        return UploadedDocument.objects.create(
            path=path,
            original_name=re.sub(
                r"[\x00-\x1f\x7f]", "", Path(upload.name.replace("\\", "/")).name
            )[:240],
            mime=mime,
            size=upload.size,
            created_by=user if user and user.is_authenticated else None,
        )
    except Exception:
        private_storage().delete(path)
        raise


def find_file(path):
    raw = unquote(str(path or "").lstrip("/"))
    if not raw or "\\" in raw or "\x00" in raw or ".." in Path(raw).parts:
        raise Http404
    roots = [Path(settings.PRIVATE_MEDIA_ROOT), Path(settings.BASE_DIR) / "static"]
    for root in roots:
        candidates = [root / raw]
        if raw.startswith("uploads/"):
            candidates.extend(
                root / folder / Path(raw).name
                for folder in [
                    "publications",
                    "professeurs",
                    "gallery",
                    "galerie",
                    "medias",
                    "covers",
                ]
            )
        for p in candidates:
            try:
                p.resolve().relative_to(root.resolve())
            except ValueError:
                continue
            if p.is_file():
                return p
    raise Http404("Fichier introuvable.")


def _file_chunks(path, start, length):
    with path.open("rb") as stream:
        stream.seek(start)
        while length > 0:
            block = stream.read(min(length, 64 * 1024))
            if not block:
                break
            length -= len(block)
            yield block


def file_response(path, filename=None, mime=None, download=False, request=None):
    p = find_file(path)
    content_type = mime or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    inline = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "video/mp4",
        "video/webm",
    }
    if content_type not in inline:
        download = True
        content_type = "application/octet-stream"
    size = p.stat().st_size
    header = request.headers.get("Range", "") if request else ""
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header) if len(header) <= 100 else None
    if match and any(match.groups()):
        first, last = match.groups()
        start = int(first) if first else max(0, size - int(last))
        end = min(int(last), size - 1) if first and last else size - 1
        if start >= size or end < start or (not first and int(last) == 0):
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
        else:
            length = end - start + 1
            body = () if request.method == "HEAD" else _file_chunks(p, start, length)
            response = StreamingHttpResponse(
                body, status=206, content_type=content_type
            )
            response["Content-Length"] = str(length)
            response["Content-Range"] = f"bytes {start}-{end}/{size}"
            response["Content-Disposition"] = content_disposition_header(
                download, filename or p.name
            )
    else:
        response = FileResponse(
            p.open("rb"),
            as_attachment=download,
            filename=filename or p.name,
            content_type=content_type,
        )
    response["Accept-Ranges"] = "bytes"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
