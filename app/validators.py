import warnings
from pathlib import Path

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 8000
MAX_IMAGE_PIXELS = 25_000_000
ALLOWED_IMAGE_FORMATS = {
    '.jpeg': 'JPEG',
    '.jpg': 'JPEG',
    '.png': 'PNG',
    '.webp': 'WEBP',
}


def validate_image_upload(upload):
    """Validate uploaded image bytes instead of trusting its name or MIME header."""
    if not upload or getattr(upload, '_committed', False):
        return

    if upload.size > MAX_IMAGE_UPLOAD_SIZE:
        raise ValidationError('A imagem deve ter no máximo 5 MB.')

    expected_format = ALLOWED_IMAGE_FORMATS.get(Path(upload.name).suffix.lower())
    if expected_format is None:
        raise ValidationError('Envie uma imagem JPG, PNG ou WEBP.')

    original_position = upload.tell()
    try:
        upload.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload) as image:
                if image.format != expected_format:
                    raise ValidationError('A extensão do arquivo não corresponde à imagem enviada.')
                width, height = image.size
                if (
                    width <= 0
                    or height <= 0
                    or width > MAX_IMAGE_DIMENSION
                    or height > MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise ValidationError('A imagem possui dimensões maiores que o permitido.')
                image.verify()
    except ValidationError:
        raise
    except (Image.DecompressionBombWarning, UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ValidationError('O arquivo enviado não é uma imagem válida.') from error
    finally:
        upload.seek(original_position)
