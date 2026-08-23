from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

from apps.courses.models import Course

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "certificate"
BLOB_1 = ASSETS_DIR / "blob-1.png"
BLOB_2 = ASSETS_DIR / "blob-2.png"
LOGO = ASSETS_DIR / "logo.png"

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT_REGULAR_PATH = str(FONTS_DIR / "DejaVuSans.ttf")
FONT_BOLD_PATH = str(FONTS_DIR / "DejaVuSans-Bold.ttf")

# Rendered 1:1 with the Figma artboard (1415x1985 px, ~170dpi at A4-ish size),
# crisp enough to print, small enough to stay a lightweight download.
CANVAS_W, CANVAS_H = 1415, 1985
# Physical PDF page size in points (the wrapped PDF is just this raster image,
# scaled down from px to a printable page, independent of image resolution).
PDF_SCALE = 0.42
PDF_W, PDF_H = CANVAS_W * PDF_SCALE, CANVAS_H * PDF_SCALE

THUMBNAIL_SIZE = (520, 730)  # 2x the 260x365 card size for retina display

BLUE = (0, 58, 255, 255)
BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
GRAY_TEXT = (61, 61, 61, 255)
PILL_BG = (167, 186, 250, 102)  # 0.4 alpha
PANEL_BG = (255, 255, 255, 153)  # 0.6 alpha

GRADIENT_STOPS = [
    (0.0, (167, 186, 250)),
    (0.5096, (252, 196, 195)),
    (1.0, (255, 244, 218)),
]

COURSE_TYPE_WORD = {
    Course.CourseTypeChoices.PROFESSION: "professional",
    Course.CourseTypeChoices.QUALIFICATION: "qualification",
    Course.CourseTypeChoices.KNOWLEDGE: "knowledge",
}


@lru_cache(maxsize=None)
def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD_PATH if bold else FONT_REGULAR_PATH, size)


class CertificateService:
    """Renders the course-completion certificate as a raster image and wraps it in a PDF for download."""

    @classmethod
    def render_preview_pdf(cls, course: Course) -> bytes:
        teacher_profile = getattr(course, "teacher_profile", None)
        image = cls._render_image(
            student_name="Student Name",
            course_title=course.title,
            course_type=course.course_type,
            certificate_description=course.certificate_description,
            duration_hours=course.duration_hours,
            focus_text=cls._focus_text(course),
            teacher_name=teacher_profile.user.get_full_name() if teacher_profile else "",
            teacher_specialization=teacher_profile.specialization if teacher_profile else "",
            signature_file=teacher_profile.signature if teacher_profile else None,
            completed_at=timezone.now(),
        )
        return cls._wrap_as_pdf(image)

    @classmethod
    def render_certificate_assets(
        cls, *, course: Course, student_name: str, course_title: str,
        teacher_name: str, completed_at,
    ) -> tuple[bytes, bytes]:
        """Takes the snapshot values explicitly rather than a CourseCompletion,
        because certificates issued by hand have no completion behind them."""
        teacher_profile = getattr(course, "teacher_profile", None)
        image = cls._render_image(
            student_name=student_name,
            course_title=course_title,
            course_type=course.course_type,
            certificate_description=course.certificate_description,
            duration_hours=course.duration_hours,
            focus_text=cls._focus_text(course),
            teacher_name=teacher_name,
            teacher_specialization=teacher_profile.specialization if teacher_profile else "",
            signature_file=teacher_profile.signature if teacher_profile else None,
            completed_at=completed_at,
        )
        return cls._wrap_as_pdf(image), cls._thumbnail(image)

    @staticmethod
    def _focus_text(course: Course) -> str:
        tag_names = [t.name for t in course.tags.all()]
        if tag_names:
            return ", ".join(tag_names)
        if course.category_id:
            return course.category.name_en
        return ""


    @classmethod
    def _render_image(
        cls, *, student_name, course_title, course_type, certificate_description,
        duration_hours, focus_text, teacher_name, teacher_specialization,
        signature_file, completed_at,
    ) -> Image.Image:
        canvas = cls._gradient_background(CANVAS_W, CANVAS_H)
        cls._draw_blobs(canvas)
        cls._draw_panel(canvas)
        cls._draw_logo_box(canvas)
        cls._draw_heading(canvas)
        cls._draw_certify_block(canvas, student_name, course_title, course_type, certificate_description)
        cls._draw_meta_rows(canvas, teacher_name, teacher_specialization, duration_hours, focus_text)
        cls._draw_date(canvas, completed_at)
        cls._draw_signature(canvas, teacher_name, signature_file)
        return canvas.convert("RGB")

    @staticmethod
    def _wrap_as_pdf(image: Image.Image) -> bytes:
        png_buffer = io.BytesIO()
        image.save(png_buffer, format="PNG")
        png_buffer.seek(0)

        pdf_buffer = io.BytesIO()
        c = pdfcanvas.Canvas(pdf_buffer, pagesize=(PDF_W, PDF_H))
        c.drawImage(ImageReader(png_buffer), 0, 0, width=PDF_W, height=PDF_H)
        c.showPage()
        c.save()
        return pdf_buffer.getvalue()

    @staticmethod
    def _thumbnail(image: Image.Image) -> bytes:
        thumb = image.copy()
        thumb.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
        buffer = io.BytesIO()
        thumb.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()


    @staticmethod
    def _gradient_background(w: int, h: int) -> Image.Image:
        canvas = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        stops = GRADIENT_STOPS
        row = Image.new("RGBA", (w, 1))
        pixels = row.load()
        for x in range(w):
            t = x / (w - 1)
            for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
                if t0 <= t <= t1:
                    frac = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                    color = tuple(
                        round(c0[i] + (c1[i] - c0[i]) * frac) for i in range(3)
                    )
                    pixels[x, 0] = (*color, 255)
                    break
        canvas.paste(row.resize((w, h)), (0, 0))
        return canvas

    @staticmethod
    @lru_cache(maxsize=None)
    def _prepared_sprite(path: Path, w: int, h: int, angle: float) -> Image.Image | None:
        """Decode + resize + rotate a static decorative asset once; every render reuses it."""
        if not path.exists():
            return None
        sprite = Image.open(path).convert("RGBA").resize((w, h), Image.LANCZOS)
        return sprite.rotate(angle, expand=True, resample=Image.BICUBIC)

    @classmethod
    def _paste_rotated(cls, canvas: Image.Image, path: Path, *, left, top, w, h, angle) -> None:
        sprite = cls._prepared_sprite(path, round(w), round(h), angle)
        if sprite is None:
            return
        cx, cy = left + w / 2, top + h / 2
        paste_x = round(cx - sprite.width / 2)
        paste_y = round(cy - sprite.height / 2)
        canvas.alpha_composite(sprite, (paste_x, paste_y))

    @classmethod
    def _draw_blobs(cls, canvas: Image.Image) -> None:
        cls._paste_rotated(canvas, BLOB_1, left=-176, top=1450, w=726.22, h=614.02, angle=-180)
        cls._paste_rotated(canvas, BLOB_2, left=783, top=1740, w=657.1, h=555.33, angle=128.63)

    @staticmethod
    def _draw_panel(canvas: Image.Image) -> None:
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rounded_rectangle([60, 71, 60 + 1295, 71 + 1864], radius=20, fill=PANEL_BG)
        canvas.alpha_composite(overlay)

    @staticmethod
    def _draw_logo_box(canvas: Image.Image) -> None:
        # Right edge pinned to the panel's inner right margin (60 + 1295 = 1355
        # is the panel edge). No background box: the logo's own transparency
        # sits directly on the gradient/panel.
        right, top, target_h = 1295, 105, 170

        if not LOGO.exists():
            draw = ImageDraw.Draw(canvas)
            left = right - 180
            draw.text((left + 90, top + 30), "NEXO4YOU", font=_font(True, 20), fill=BLACK, anchor="mm")
            return

        logo = Image.open(LOGO).convert("RGBA")
        target_w = target_h * logo.width / logo.height
        logo = logo.resize((round(target_w), round(target_h)), Image.LANCZOS)
        canvas.alpha_composite(logo, (round(right - target_w), round(top)))

    @staticmethod
    def _draw_heading(canvas: Image.Image) -> None:
        draw = ImageDraw.Draw(canvas)
        font = _font(True, 72)
        line_h = 72 * 1.10
        draw.text((120, 380), "CERTIFICATE", font=font, fill=BLUE, anchor="la")
        draw.text((120, 380 + line_h), "OF COMPLETION", font=font, fill=BLUE, anchor="la")

    @classmethod
    def _draw_certify_block(cls, canvas, student_name, course_title, course_type, certificate_description) -> None:
        draw = ImageDraw.Draw(canvas)
        draw.text((120, 598), "This is to certify that", font=_font(False, 36), fill=BLACK, anchor="la")
        draw.text((120, 651), student_name, font=_font(True, 36), fill=BLACK, anchor="la")

        word = COURSE_TYPE_WORD.get(course_type, "")
        draw.text(
            (120, 724), f"has successfully completed the {word} course".strip(),
            font=_font(False, 32), fill=BLACK, anchor="la",
        )

        pill_left, pill_top, pill_w, pill_h = 120, 772, 731, 40
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rounded_rectangle(
            [pill_left, pill_top, pill_left + pill_w, pill_top + pill_h], radius=4, fill=PILL_BG,
        )
        canvas.alpha_composite(overlay)
        title_font = _font(False, 32)
        title_text = cls._ellipsize(course_title, title_font, pill_w - 24)
        draw.text((pill_left + 12, pill_top + pill_h / 2), title_text, font=title_font, fill=BLUE, anchor="lm")

        if certificate_description:
            desc_font = _font(False, 32)
            lines = cls._wrap_text(certificate_description, desc_font, 1175)[:3]
            for i, line in enumerate(lines):
                draw.text((120, 872 + i * 40), line, font=desc_font, fill=GRAY_TEXT, anchor="la")

    @staticmethod
    def _draw_meta_rows(canvas, teacher_name, teacher_specialization, duration_hours, focus_text) -> None:
        draw = ImageDraw.Draw(canvas)
        instructor = teacher_name
        if teacher_specialization:
            instructor = f"{instructor} ({teacher_specialization})"
        duration = f"{duration_hours} hours" if duration_hours else "Self-paced"

        rows = [("Instructor:", instructor), ("Duration:", duration)]
        if focus_text:
            rows.append(("Focus:", focus_text))

        label_font = _font(True, 24)
        value_font = _font(False, 24)
        row_top = 1052
        for label, value in rows:
            draw.text((120, row_top), label, font=label_font, fill=BLACK, anchor="la")
            label_w = draw.textlength(label, font=label_font)
            draw.text((120 + label_w + 8, row_top), value, font=value_font, fill=BLACK, anchor="la")
            row_top += 34

    @staticmethod
    def _draw_date(canvas, completed_at) -> None:
        draw = ImageDraw.Draw(canvas)
        font = _font(False, 24)
        draw.text((120, 1327), "Date:", font=font, fill=BLACK, anchor="la")
        date_x = 120 + draw.textlength("Date:", font=font) + 8
        date_text = timezone.localtime(completed_at).strftime("%d/%m/%Y") if completed_at else ""
        draw.text((date_x, 1327), date_text, font=font, fill=BLACK, anchor="la")
        underline_y = 1327 + 30
        draw.line([(date_x, underline_y), (date_x + 150, underline_y)], fill=BLACK, width=2)

    @staticmethod
    def _draw_signature(canvas, teacher_name, signature_file) -> None:
        line_left, line_top, line_w = 995, 1357, 300
        center_x = line_left + line_w / 2

        draw = ImageDraw.Draw(canvas)
        draw.line([(line_left, line_top), (line_left + line_w, line_top)], fill=BLACK, width=2)

        if signature_file:
            try:
                sig = Image.open(signature_file.open("rb")).convert("RGBA")
                iw, ih = sig.size
                # Fills most of the blank gap above the line (Focus row ends well
                # above line_top), a small signature reads as an afterthought.
                # Sits low enough to slightly cross the line, like a real signature.
                target_h = 220
                target_w = min(line_w * 1.3, target_h * iw / ih)
                sig = sig.resize((round(target_w), round(target_h)), Image.LANCZOS)
                canvas.alpha_composite(
                    sig, (round(center_x - target_w / 2), round(line_top - target_h + 20)),
                )
            except (OSError, ValueError):
                pass

        font = _font(True, 24)
        draw.text((center_x, line_top + 32), teacher_name, font=font, fill=BLACK, anchor="ma")
        draw.text((center_x, line_top + 32 + 24 * 1.25), "Instructor", font=font, fill=BLACK, anchor="ma")


    @staticmethod
    def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if font.getlength(candidate) <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def _ellipsize(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> str:
        if font.getlength(text) <= max_width:
            return text
        while text and font.getlength(text + "…") > max_width:
            text = text[:-1]
        return text + "…"
