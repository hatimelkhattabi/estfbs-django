from io import BytesIO
from pathlib import Path
import uuid
from PIL import Image, ImageOps, ImageDraw, ImageFont
from django.conf import settings
from django.core.files.base import ContentFile
from .files import private_storage


def create_cover(background, logo, title, subtitle, footer):
    with Image.open(background) as source:
        image = ImageOps.fit(
            ImageOps.exif_transpose(source).convert("RGB"), (1000, 600)
        )
    image = Image.blend(image, Image.new("RGB", image.size, "white"), 0.78)
    if logo:
        with Image.open(logo) as source:
            mark = ImageOps.exif_transpose(source).convert("RGBA")
            mark.thumbnail((180, 150))
            image.paste(mark, ((1000 - mark.width) // 2, 35), mark)
    draw = ImageDraw.Draw(image)

    def font(size, bold=False):
        path = (
            Path(settings.BASE_DIR)
            / "static/fonts"
            / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
        )
        return (
            ImageFont.truetype(str(path), size)
            if path.exists()
            else ImageFont.load_default(size=size)
        )

    def centered(text, y, size, bold=False):
        f = font(size, bold)
        while draw.textlength(text, font=f) > 900 and size > 15:
            size -= 1
            f = font(size, bold)
        draw.text(
            (500, y),
            text,
            font=f,
            fill="#0b1a38" if not bold else "#111111",
            anchor="mt",
        )

    centered(title, 220, 66, True)
    centered(subtitle, 320, 40, True)
    draw.line((365, 403, 635, 403), fill="#c4a15c", width=4)
    centered(footer, 438, 30)
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=90)
    return private_storage().save(
        "covers/" + uuid.uuid4().hex + ".jpg", ContentFile(buf.getvalue())
    )
