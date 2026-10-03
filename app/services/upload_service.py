import os
from io import BytesIO
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}


class InvalidUploadError(ValueError):
    pass


def read_validated_image(file_storage, max_bytes=5 * 1024 * 1024):
    """Validate and normalize a DB-stored service/package image to JPEG."""
    extension = os.path.splitext(secure_filename(file_storage.filename or ''))[1].lower()
    mime = (file_storage.mimetype or '').lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS or mime not in ALLOWED_IMAGE_MIME_TYPES:
        raise InvalidUploadError('Chỉ chấp nhận ảnh JPG, PNG hoặc WEBP có MIME hợp lệ')
    data = file_storage.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise InvalidUploadError('Ảnh vượt quá giới hạn 5 MB')
    try:
        with Image.open(BytesIO(data)) as image:
            expected = {'JPEG': ('image/jpeg', {'.jpg', '.jpeg'}), 'PNG': ('image/png', {'.png'}), 'WEBP': ('image/webp', {'.webp'})}.get(image.format)
            if not expected or mime != expected[0] or extension not in expected[1] or image.width * image.height > 20000000:
                raise InvalidUploadError('Định dạng hoặc kích thước ảnh không hợp lệ')
            image.load()
            image.thumbnail((1600, 1600))
            output = BytesIO()
            image.convert('RGB').save(output, format='JPEG', quality=88)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise InvalidUploadError('Nội dung tệp không phải ảnh hợp lệ')


def save_validated_image(file_storage, upload_folder, filename_prefix):
    """Validate an uploaded image and save it under a collision-safe name."""
    if not file_storage or not file_storage.filename:
        raise InvalidUploadError("Vui lòng chọn tệp ảnh")
    if not upload_folder:
        raise RuntimeError("UPLOAD_FOLDER chưa được cấu hình")

    safe_original = secure_filename(file_storage.filename)
    extension = os.path.splitext(safe_original)[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise InvalidUploadError("Chỉ chấp nhận ảnh JPG, JPEG, PNG hoặc WEBP")

    content_type = (file_storage.mimetype or "").lower()
    if content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise InvalidUploadError("MIME type của tệp ảnh không hợp lệ")

    try:
        file_storage.stream.seek(0)
        with Image.open(file_storage.stream) as image:
            detected_format = (image.format or "").upper()
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise InvalidUploadError("Nội dung tệp không phải ảnh hợp lệ")
    finally:
        file_storage.stream.seek(0)

    if detected_format not in ALLOWED_PIL_FORMATS:
        raise InvalidUploadError("Định dạng ảnh không được hỗ trợ")
    if detected_format == "JPEG" and extension not in {".jpg", ".jpeg"}:
        raise InvalidUploadError("Phần mở rộng không khớp nội dung ảnh")
    if detected_format == "PNG" and extension != ".png":
        raise InvalidUploadError("Phần mở rộng không khớp nội dung ảnh")
    if detected_format == "WEBP" and extension != ".webp":
        raise InvalidUploadError("Phần mở rộng không khớp nội dung ảnh")

    os.makedirs(upload_folder, exist_ok=True)
    safe_prefix = secure_filename(filename_prefix) or "image"
    filename = f"{safe_prefix}_{uuid4().hex}{extension}"
    file_storage.save(os.path.join(upload_folder, filename))
    return filename
