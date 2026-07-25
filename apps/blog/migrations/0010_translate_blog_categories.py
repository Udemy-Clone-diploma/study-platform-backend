from django.db import migrations

# Translates the 8 categories seeded by migrations 0002_seed_categories /
# 0005_blogcategory_headline. A custom category an admin adds later has
# nothing to translate here -- this is a one-time backfill for the seed set.
TRANSLATIONS = {
    "student-stories": {
        "name_uk": "Історії студентів",
        "name_fr": "Témoignages d'étudiants",
        "name_es": "Historias de estudiantes",
        "name_de": "Studierendengeschichten",
        "headline_uk": "Історії зростання та нових починань",
        "headline_fr": "Histoires de croissance et de nouveaux départs",
        "headline_es": "Historias de crecimiento y nuevos comienzos",
        "headline_de": "Geschichten von Wachstum und Neuanfängen",
        "description_uk": "Історії студентів, зміни кар'єри, досвід навчання",
        "description_fr": "Témoignages d'étudiants, changements de carrière, expériences d'apprentissage",
        "description_es": "Historias de estudiantes, cambios de carrera, experiencias de aprendizaje",
        "description_de": "Geschichten von Studierenden, Karrierewechsel, Lernerfahrungen",
    },
    "career-growth": {
        "name_uk": "Кар'єрне зростання",
        "name_fr": "Évolution de carrière",
        "name_es": "Crecimiento profesional",
        "name_de": "Karrierewachstum",
        "headline_uk": "Ваш шлях до успіху",
        "headline_fr": "Votre chemin vers la réussite",
        "headline_es": "Tu camino hacia el éxito",
        "headline_de": "Ihr Weg zum Erfolg",
        "description_uk": "Поради щодо кар'єри, розвиток навичок, фриланс",
        "description_fr": "Conseils de carrière, développement des compétences, freelance",
        "description_es": "Consejos de carrera, desarrollo de habilidades, trabajo freelance",
        "description_de": "Karrieretipps, Kompetenzentwicklung, Freelancing",
    },
    "design-creativity": {
        "name_uk": "Дизайн і творчість",
        "name_fr": "Design et créativité",
        "name_es": "Diseño y creatividad",
        "name_de": "Design & Kreativität",
        "headline_uk": "Дизайн-лабораторія",
        "headline_fr": "Labo Design",
        "headline_es": "Laboratorio de diseño",
        "headline_de": "Design-Labor",
        "description_uk": "UI/UX, графічний дизайн, тренди",
        "description_fr": "UI/UX, design graphique, tendances",
        "description_es": "UI/UX, diseño gráfico, tendencias",
        "description_de": "UI/UX, Grafikdesign, Trends",
    },
    "learning-tips": {
        "name_uk": "Поради з навчання",
        "name_fr": "Conseils d'apprentissage",
        "name_es": "Consejos de estudio",
        "name_de": "Lerntipps",
        "headline_uk": "Навчайся розумно",
        "headline_fr": "Étudiez intelligemment",
        "headline_es": "Estudia de forma inteligente",
        "headline_de": "Klug lernen",
        "description_uk": "Поради щодо навчання та продуктивності",
        "description_fr": "Conseils pour étudier et être productif",
        "description_es": "Consejos para estudiar y ser productivo",
        "description_de": "Tipps zum Lernen und für mehr Produktivität",
    },
    "industry-insights": {
        "name_uk": "Огляд індустрії",
        "name_fr": "Regards sur l'industrie",
        "name_es": "Perspectivas del sector",
        "name_de": "Brancheneinblicke",
        "headline_uk": "Що формує індустрію",
        "headline_fr": "Ce qui façonne l'industrie",
        "headline_es": "Lo que está moldeando la industria",
        "headline_de": "Was die Branche prägt",
        "description_uk": "Новини та тренди галузі",
        "description_fr": "Actualités et tendances du secteur",
        "description_es": "Noticias y tendencias del sector",
        "description_de": "Branchennews und Trends",
    },
    "technology": {
        "name_uk": "Технології",
        "name_fr": "Technologie",
        "name_es": "Tecnología",
        "name_de": "Technologie",
        "headline_uk": "Інструменти майбутнього",
        "headline_fr": "Les outils de demain",
        "headline_es": "Las herramientas del mañana",
        "headline_de": "Werkzeuge von morgen",
        "description_uk": "ШІ, цифрові інструменти, статті про технології",
        "description_fr": "IA, outils numériques, articles tech",
        "description_es": "IA, herramientas digitales, artículos de tecnología",
        "description_de": "KI, digitale Tools, Tech-Artikel",
    },
    "productivity": {
        "name_uk": "Продуктивність",
        "name_fr": "Productivité",
        "name_es": "Productividad",
        "name_de": "Produktivität",
        "headline_uk": "Працюй розумніше, а не більше",
        "headline_fr": "Travaillez plus intelligemment, pas plus dur",
        "headline_es": "Trabaja de forma más inteligente, no más duro",
        "headline_de": "Klüger arbeiten, nicht härter",
        "description_uk": "Організація роботи, тайм-менеджмент",
        "description_fr": "Organisation du travail, gestion du temps",
        "description_es": "Organización del trabajo, gestión del tiempo",
        "description_de": "Arbeitsorganisation, Zeitmanagement",
    },
    "community": {
        "name_uk": "Спільнота",
        "name_fr": "Communauté",
        "name_es": "Comunidad",
        "name_de": "Community",
        "headline_uk": "Життя на платформі",
        "headline_fr": "La vie sur la plateforme",
        "headline_es": "La vida en la plataforma",
        "headline_de": "Leben auf der Plattform",
        "description_uk": "Події, інтерв'ю, життя платформи",
        "description_fr": "Événements, interviews, vie de la plateforme",
        "description_es": "Eventos, entrevistas, vida de la plataforma",
        "description_de": "Events, Interviews, Plattformleben",
    },
}


def translate_categories(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    for slug, fields in TRANSLATIONS.items():
        BlogCategory.objects.filter(slug=slug).update(**fields)


def untranslate_categories(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    blank = {
        f"{base}_{locale}": ""
        for base in ("name", "headline", "description")
        for locale in ("uk", "fr", "es", "de")
    }
    BlogCategory.objects.filter(slug__in=TRANSLATIONS.keys()).update(**blank)


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0009_blogcategory_finalize_locale_fields"),
    ]

    operations = [
        migrations.RunPython(translate_categories, untranslate_categories),
    ]
