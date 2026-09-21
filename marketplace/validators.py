import re
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 6000


def validate_cameroon_phone(value: str) -> str:
    normalized = normalize_cameroon_phone(value)
    if not re.fullmatch(r"\+237[2-6]\d{8}", normalized):
        raise ValidationError("Saisissez un numéro camerounais valide, par exemple 6 99 12 34 56.")
    return normalized


def normalize_cameroon_phone(value: str) -> str:
    value = "".join(str(value or "").split())
    if value.startswith("00"):
        value = "+" + value[2:]
    elif value.startswith("237") and not value.startswith("+237"):
        value = "+" + value
    elif value.startswith("6") and len(value) == 9:
        value = "+237" + value
    return value


def validate_image_upload(uploaded_file):
    if not uploaded_file:
        return
    if uploaded_file.size > MAX_IMAGE_SIZE:
        raise ValidationError("Chaque image doit faire 5 Mo maximum.")
    content_type = getattr(uploaded_file, "content_type", "")
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError("Formats acceptés : JPG, PNG et WEBP.")
    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.verify()
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        width, height = image.size
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise ValidationError("L'image est trop grande. 6000 × 6000 pixels maximum.")
        if image.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValidationError("Formats acceptés : JPG, PNG et WEBP.")
        uploaded_file.seek(0)
    except UnidentifiedImageError as exc:
        raise ValidationError("Le fichier envoyé n'est pas une image valide.") from exc
    except OSError as exc:
        raise ValidationError("Impossible de lire cette image.") from exc
