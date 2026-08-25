"""Attach demo images and files to the rows `manage.py seed` created.

Kept apart from `seed` on purpose:

  * it needs the network (once, to fetch avatars) and must not run inside a
    transaction, since bytes written to storage are not rolled back with it;
  * files land wherever the *running environment* points, so the same database
    needs this run once per environment. With DEBUG=True everything goes to
    <repo>/media/ on this machine; with DEBUG=False it goes to the S3 bucket.
    Rows are untouched either way, so re-running it elsewhere is safe.

    python manage.py seed_media --download   # once: fetch avatars into assets/
    python manage.py seed_media              # attach everything
    python manage.py seed_media --force      # replace files that are already set
    python manage.py seed_media --only covers

Avatars come from DiceBear and are committed under apps/common/assets/seed/, so
nothing depends on a third-party API being reachable on demo day. Course covers,
teacher signatures, and lesson documents are generated locally with Pillow and
reportlab, both of which the project already depends on.
"""

import hashlib
import io
from pathlib import Path

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdfcanvas

from apps.courses.models import ApprovedCourseRecord, Course, RejectedCourseRecord
from apps.curriculum.models import LessonDocument
from apps.users.models import TeacherProfile, User

from ._seed_data import ADMIN, MODERATORS, STUDENTS, TEACHERS

ASSETS_DIR = Path(settings.BASE_DIR) / "apps" / "common" / "assets" / "seed"
AVATARS_DIR = ASSETS_DIR / "avatars"
LOGO_PATH = Path(settings.BASE_DIR) / "apps" / "common" / "assets" / "logo" / "nexo4u_logo.png"
FONTS_DIR = Path(settings.BASE_DIR) / "apps" / "enrollments" / "assets" / "fonts"
FONT_REGULAR = str(FONTS_DIR / "DejaVuSans.ttf")
FONT_BOLD = str(FONTS_DIR / "DejaVuSans-Bold.ttf")

# Notionists is CC0 1.0 (designer Zoish). Other DiceBear collections are not:
# bottts, for one, ships a bespoke "free for personal and commercial use" term.
# If you swap the style, update assets/seed/LICENSE.md with the new one.
AVATAR_STYLE = "notionists"
AVATAR_SOURCE = "https://api.dicebear.com/9.x/{style}/png?seed={seed}&size=256"
AVATAR_LICENSE = """# Seed avatar assets

Style: DiceBear "notionists" (https://www.dicebear.com/styles/notionists/)
Designer: Zoish (https://bio.link/heyzoish)
Design license: CC0 1.0 (https://creativecommons.org/publicdomain/zero/1.0/)

Generated with the DiceBear HTTP API and committed here so the demo has no
runtime dependency on a third-party service. Regenerate with:

    python manage.py seed_media --download
"""

COVER_SIZE = (1200, 675)
# Deterministic per course: the slug hash picks one pair.
COVER_GRADIENTS = [
    ((32, 58, 138), (59, 130, 246)),
    ((22, 78, 99), (13, 148, 136)),
    ((76, 29, 149), (139, 92, 246)),
    ((131, 24, 67), (219, 39, 119)),
    ((120, 53, 15), (245, 158, 11)),
    ((20, 83, 45), (34, 197, 94)),
]

GROUPS = ("avatars", "covers", "signatures", "documents")


class Command(BaseCommand):
    help = "Attach avatars, course covers, teacher signatures, and lesson documents."

    def add_arguments(self, parser):
        parser.add_argument(
            "--download",
            action="store_true",
            help="Fetch avatar PNGs into apps/common/assets/seed/ and exit.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace files that are already set instead of skipping them.",
        )
        parser.add_argument(
            "--only",
            choices=GROUPS,
            action="append",
            help="Limit the run to one group; repeatable.",
        )

    def handle(self, *args, **options):
        self.force = options["force"]
        if options["download"]:
            self._download()
            return

        groups = options["only"] or GROUPS
        # No transaction: a rollback after a file is written would leave orphaned
        # bytes in storage with no row pointing at them.
        if "avatars" in groups:
            self._avatars()
        if "covers" in groups:
            self._covers()
        if "signatures" in groups:
            self._signatures()
        if "documents" in groups:
            self._documents()

    def _download(self):
        AVATARS_DIR.mkdir(parents=True, exist_ok=True)
        (ASSETS_DIR / "LICENSE.md").write_text(AVATAR_LICENSE, encoding="utf-8")
        fetched = skipped = 0
        for email in self._demo_emails():
            target = AVATARS_DIR / f"{email.split('@')[0]}.png"
            if target.exists() and not self.force:
                skipped += 1
                continue
            url = AVATAR_SOURCE.format(style=AVATAR_STYLE, seed=email)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            target.write_bytes(response.content)
            fetched += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Avatars: {fetched} downloaded, {skipped} already present, in {AVATARS_DIR}. "
                "Commit them so demo day needs no network."
            )
        )

    @staticmethod
    def _demo_emails():
        return [ADMIN["email"]] + [person["email"] for person in MODERATORS + TEACHERS + STUDENTS]

    def _avatars(self):
        if not AVATARS_DIR.exists():
            self.stdout.write(
                self.style.WARNING(
                    "No avatar assets yet. Run `python manage.py seed_media --download` first."
                )
            )
            return
        attached = 0
        for email in self._demo_emails():
            user = User.all_objects.filter(email=email).first()
            source = AVATARS_DIR / f"{email.split('@')[0]}.png"
            if user is None or not source.exists() or not self._needs_file(user.avatar):
                continue
            with source.open("rb") as handle:
                user.avatar.save(source.name, ContentFile(handle.read()), save=True)
            attached += 1
        self.stdout.write(f"  avatars: {attached} attached")

    def _covers(self):
        attached = 0
        for course in Course.all_objects.all():
            if not self._needs_file(course.image):
                continue
            image = self._render_cover(course)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            course.image.save(f"{course.slug}.png", ContentFile(buffer.getvalue()), save=True)
            self._backfill_record_images(course)
            attached += 1
        self.stdout.write(f"  covers: {attached} generated")

    @staticmethod
    def _backfill_record_images(course):
        """Approval and rejection records freeze the cover URL at decision time.

        The seed command writes those records before this command gives the
        course an image, so their snapshot is empty and the moderator's history
        screens show a course with no icon. Only blank snapshots are filled, so
        a record that captured an earlier cover keeps it.
        """
        url = course.image.url
        for model in (ApprovedCourseRecord, RejectedCourseRecord):
            model.objects.filter(course=course, course_image_url__isnull=True).update(
                course_image_url=url
            )
            model.objects.filter(course=course, course_image_url="").update(course_image_url=url)

    def _signatures(self):
        attached = 0
        for profile in TeacherProfile.objects.select_related("user"):
            if not self._needs_file(profile.signature):
                continue
            image = self._render_signature(profile.user.get_full_name())
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            profile.signature.save(
                f"signature-{profile.pk}.png", ContentFile(buffer.getvalue()), save=True
            )
            attached += 1
        self.stdout.write(f"  signatures: {attached} generated")

    def _documents(self):
        attached = 0
        for document in LessonDocument.objects.select_related("lesson__module__course"):
            if not self._needs_file(document.file):
                continue
            course = document.lesson.module.course
            pdf = self._render_document(document.original_name, course.title, document.lesson.title)
            document.file.save(
                f"{document.pk}-{document.original_name}.pdf", ContentFile(pdf), save=True
            )
            attached += 1
        self.stdout.write(f"  documents: {attached} generated")

    def _needs_file(self, field_file):
        """True when the column has no usable file behind it.

        A truthy FieldFile only means the column holds a name. The seeder writes a
        placeholder path for lesson documents, and a database seeded against a
        different storage backend points at bytes this environment cannot see, so
        the storage has to be asked as well.
        """
        if self.force:
            return True
        if not field_file:
            return True
        return not field_file.storage.exists(field_file.name)

    def _render_cover(self, course):
        width, height = COVER_SIZE
        index = int(hashlib.md5(course.slug.encode()).hexdigest(), 16) % len(COVER_GRADIENTS)
        start, end = COVER_GRADIENTS[index]
        image = Image.new("RGB", COVER_SIZE, start)
        draw = ImageDraw.Draw(image)
        for y in range(height):
            ratio = y / height
            draw.line(
                [(0, y), (width, y)],
                fill=tuple(
                    round(start[channel] + (end[channel] - start[channel]) * ratio)
                    for channel in range(3)
                ),
            )

        label = " · ".join(
            part
            for part in (
                course.category.name_en if course.category_id else "",
                course.get_level_display(),
            )
            if part
        )
        draw.text(
            (72, 72), label.upper(), font=self._font(bold=False, size=28), fill=(255, 255, 255)
        )

        font = self._font(bold=True, size=76)
        y = 190
        for line in self._wrap(draw, course.title, font, width - 144):
            draw.text((72, y), line, font=font, fill=(255, 255, 255))
            y += 92

        if course.subtitle:
            subtitle_font = self._font(bold=False, size=32)
            y += 12
            for line in self._wrap(draw, course.subtitle, subtitle_font, width - 144)[:2]:
                draw.text((72, y), line, font=subtitle_font, fill=(226, 232, 240))
                y += 44

        if LOGO_PATH.exists():
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo.thumbnail((160, 160))
            box = (width - logo.width - 72, height - logo.height - 60)
            # The wordmark is dark navy, so it needs a light plate to stay legible
            # on the darker gradients.
            plate = Image.new("RGBA", (logo.width + 48, logo.height + 36), (255, 255, 255, 0))
            ImageDraw.Draw(plate).rounded_rectangle(
                [(0, 0), (plate.width - 1, plate.height - 1)],
                radius=18,
                fill=(255, 255, 255, 214),
            )
            image.paste(plate, (box[0] - 24, box[1] - 18), plate)
            image.paste(logo, box, logo)
        return image

    def _render_signature(self, name):
        image = Image.new("RGBA", (600, 200), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        font = self._font(bold=False, size=54)
        draw.text((40, 55), name, font=font, fill=(15, 23, 42, 255))
        draw.line([(40, 140), (560, 140)], fill=(15, 23, 42, 255), width=3)
        # A slight shear reads as handwriting rather than a typed label.
        return image.transform(
            image.size, Image.AFFINE, (1, -0.22, 30, 0, 1, 0), resample=Image.BICUBIC
        )

    def _render_document(self, title, course_title, lesson_title):
        buffer = io.BytesIO()
        pdf = pdfcanvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(2.5 * cm, height - 3 * cm, title.rsplit(".", 1)[0])
        pdf.setFont("Helvetica", 11)
        pdf.drawString(2.5 * cm, height - 3.9 * cm, f"{course_title} — {lesson_title}")
        pdf.line(2.5 * cm, height - 4.3 * cm, width - 2.5 * cm, height - 4.3 * cm)
        text = pdf.beginText(2.5 * cm, height - 5.6 * cm)
        text.setFont("Helvetica", 11)
        for line in [
            "Worksheet for this lesson.",
            "",
            "1. Re-read the lesson summary and note the one idea you are least sure about.",
            "2. Work through the exercise in the lesson before looking at the solution.",
            "3. Write down what you would do differently on a second attempt.",
            "",
            "Bring your notes to the next live session; we start from the questions",
            "people bring rather than from the slides.",
        ]:
            text.textLine(line)
        pdf.drawText(text)
        pdf.showPage()
        pdf.save()
        return buffer.getvalue()

    @staticmethod
    def _font(*, bold, size):
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)

    @staticmethod
    def _wrap(draw, text, font, max_width):
        lines, current = [], ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
