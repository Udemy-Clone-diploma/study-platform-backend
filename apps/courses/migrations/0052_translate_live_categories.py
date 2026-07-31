from django.db import migrations

# 0051 translated the demo category set seeded by apps.common.management.commands.seed
# (Design/Marketing/Languages/IT/Business, lowercase slugs). This backend's actual dev
# database has a different, real category set (created through the admin, mixed-case
# slugs) -- translate those directly by their live slugs instead.
TRANSLATIONS = {
    "Business": {
        "name_uk": "Бізнес",
        "name_fr": "Affaires",
        "name_es": "Negocios",
        "name_de": "Wirtschaft",
        "description_uk": "Здобудьте експертизу в менеджменті, фінансах та оптимізації процесів.",
        "description_fr": "Acquérez une expertise en gestion, finance et optimisation des processus.",
        "description_es": "Adquiere experiencia en gestión, finanzas y optimización de procesos.",
        "description_de": "Erwerben Sie Fachwissen in Management, Finanzen und Prozessoptimierung.",
    },
    "Data-Science-AI": {
        "name_uk": "Наука про дані та ШІ",
        "name_fr": "Science des données et IA",
        "name_es": "Ciencia de datos e IA",
        "name_de": "Data Science & KI",
        "description_uk": "Аналізуйте дані, створюйте інтелектуальні системи та знаходьте інсайти за допомогою машинного навчання та сучасних інструментів роботи з даними.",
        "description_fr": "Analysez des données, construisez des systèmes intelligents et découvrez des informations grâce au machine learning et aux outils de données modernes.",
        "description_es": "Analiza datos, construye sistemas inteligentes y descubre información mediante el aprendizaje automático y herramientas de datos modernas.",
        "description_de": "Analysieren Sie Daten, entwickeln Sie intelligente Systeme und gewinnen Sie Erkenntnisse mit maschinellem Lernen und modernen Datentools.",
    },
    "Design-Aesthetics-UX": {
        "name_uk": "Естетика дизайну та UX",
        "name_fr": "Esthétique du design et UX",
        "name_es": "Estética del diseño y UX",
        "name_de": "Designästhetik & UX",
        "description_uk": "Навчіться створювати інтерфейси, графіку та візуальні світи.",
        "description_fr": "Apprenez à créer des interfaces, des graphismes et des univers visuels.",
        "description_es": "Aprende a crear interfaces, gráficos y mundos visuales.",
        "description_de": "Lernen Sie, Interfaces, Grafiken und visuelle Welten zu gestalten.",
    },
    "IT-Cybersecurity": {
        "name_uk": "ІТ та кібербезпека",
        "name_fr": "Informatique et cybersécurité",
        "name_es": "TI y ciberseguridad",
        "name_de": "IT & Cybersicherheit",
        "description_uk": "Навчіться керувати системами, працювати з хмарними технологіями та захищати дані від кіберзагроз",
        "description_fr": "Apprenez à gérer des systèmes, à travailler avec les technologies cloud et à protéger les données contre les cybermenaces",
        "description_es": "Aprende a administrar sistemas, trabajar con tecnologías en la nube y proteger los datos de las ciberamenazas",
        "description_de": "Lernen Sie, Systeme zu verwalten, mit Cloud-Technologien zu arbeiten und Daten vor Cyberbedrohungen zu schützen",
    },
    "Languages": {
        "name_uk": "Мови",
        "name_fr": "Langues",
        "name_es": "Idiomas",
        "name_de": "Sprachen",
        "description_uk": "Вивчайте іноземні мови для кар'єри, подорожей та спілкування.",
        "description_fr": "Apprenez des langues étrangères pour votre carrière, vos voyages et la communication.",
        "description_es": "Aprende idiomas extranjeros para tu carrera, viajes y comunicación.",
        "description_de": "Lernen Sie Fremdsprachen für Karriere, Reisen und Kommunikation.",
    },
    "Marketing-Strategy": {
        "name_uk": "Маркетингова стратегія",
        "name_fr": "Stratégie marketing",
        "name_es": "Estrategia de marketing",
        "name_de": "Marketingstrategie",
        "description_uk": "Дізнайтеся, як просувати бренди та залучати тисячі клієнтів.",
        "description_fr": "Découvrez comment promouvoir des marques et attirer des milliers de clients.",
        "description_es": "Descubre cómo promocionar marcas y atraer a miles de clientes.",
        "description_de": "Erfahren Sie, wie Sie Marken bewerben und Tausende von Kunden gewinnen.",
    },
    "Personal-development": {
        "name_uk": "Особистий розвиток",
        "name_fr": "Développement personnel",
        "name_es": "Desarrollo personal",
        "name_de": "Persönlichkeitsentwicklung",
        "description_uk": "Підвищуйте особисту ефективність, тайм-менеджмент та лідерські якості.",
        "description_fr": "Améliorez votre efficacité personnelle, votre gestion du temps et votre leadership.",
        "description_es": "Mejora tu eficiencia personal, gestión del tiempo y liderazgo.",
        "description_de": "Steigern Sie Ihre persönliche Effizienz, Ihr Zeitmanagement und Ihre Führungsqualitäten.",
    },
    "Programming-Basics-to-Pro": {
        "name_uk": "Програмування від основ до профі",
        "name_fr": "Programmation, des bases au niveau pro",
        "name_es": "Programación: de lo básico a profesional",
        "name_de": "Programmieren von den Grundlagen bis zum Profi",
        "description_uk": "Опануйте популярні мови програмування та створюйте власне програмне забезпечення.",
        "description_fr": "Maîtrisez les langages de programmation tendance et créez vos propres logiciels.",
        "description_es": "Domina los lenguajes de programación más populares y crea tu propio software.",
        "description_de": "Beherrschen Sie angesagte Programmiersprachen und entwickeln Sie Ihre eigene Software.",
    },
}


def translate_categories(apps, schema_editor):
    Category = apps.get_model("courses", "Category")
    for slug, fields in TRANSLATIONS.items():
        Category.objects.filter(slug=slug).update(**fields)


def untranslate_categories(apps, schema_editor):
    Category = apps.get_model("courses", "Category")
    blank = {
        f"{base}_{locale}": ""
        for base in ("name", "description")
        for locale in ("uk", "fr", "es", "de")
    }
    Category.objects.filter(slug__in=TRANSLATIONS.keys()).update(**blank)


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0051_translate_categories"),
    ]

    operations = [
        migrations.RunPython(translate_categories, untranslate_categories),
    ]
