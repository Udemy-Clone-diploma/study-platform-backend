"""Seed the database with demo blog articles, 8 per category, with randomly assigned authors.

Idempotent: articles are created with get_or_create on their slug, so running it
repeatedly will not duplicate rows.

    python manage.py seed_blog
    python manage.py seed_blog --cover-image /path/to/cover.png

Requires at least one teacher/moderator/administrator user to already exist
(e.g. via `python manage.py seed`), authors are picked at random from them.
"""

import random
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.blog.models import Article, BlogCategory
from apps.users.models import User

LOREM = [
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, "
    "quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore "
    "eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt "
    "in culpa qui officia deserunt mollit anim id est laborum.",
    "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium "
    "doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore.",
]

# (title, subtitle) pairs, 8 per category slug (matches apps/blog/migrations/0002_seed_categories.py).
BLOG_TOPICS: dict[str, list[tuple[str, str]]] = {
    # Student Stories are staff-authored profiles: title is the student's name, subtitle
    # is their one-line hook, and STUDENT_STORY_BODIES below carries their real narrative
    # (unlike every other category, which just gets random LOREM paragraphs).
    "student-stories": [
        (
            "Priya Sharma",
            "Five years in marketing taught me everything except how to say I wanted more — until I found UX.",
        ),
        (
            "Daniel Kim",
            "No computer science degree, no internship, no connections — just a plan and eight months of consistency.",
        ),
        (
            "Sofia Martinez",
            "Thirty-five, no technical background, and convinced it was too late — I was wrong.",
        ),
        (
            "Olena Petrenko",
            "Two years ago I was the newest bootcamp graduate on the team. Now I lead it.",
        ),
        (
            "Marcus Bailey",
            "Spreadsheets were supposed to be temporary. They turned into a career I never planned for.",
        ),
        (
            "Aiden Walsh",
            "My first paying client taught me more about freelancing than any course did — mostly through my own mistakes.",
        ),
        (
            "Grace Okafor",
            "Studying after a full workday sounded impossible until I stopped trying to do it the way everyone else did.",
        ),
        (
            "Liam Anderson",
            "No agency experience, no client work, no design job — just three side projects and a decision to start anyway.",
        ),
    ],
    "career-growth": [
        (
            "Negotiating Your First Raise",
            "A practical script for a conversation most people avoid.",
        ),
        (
            "How to Ask for a Promotion Without Feeling Awkward",
            "Framing your case around impact, not tenure.",
        ),
        (
            "Freelancing 101: Setting Rates You Won't Regret",
            "Pricing strategies for new freelancers.",
        ),
        ("Building a Personal Brand as a Developer", "Why writing in public pays off long-term."),
        ("The Skills Gap Nobody Talks About", "Soft skills that matter as much as your stack."),
        (
            "Switching Specializations Mid-Career",
            "How to reposition your experience for a new niche.",
        ),
        (
            "Networking for Introverts",
            "Low-pressure ways to build real professional relationships.",
        ),
        ("What Recruiters Actually Look For", "Insights from the other side of the hiring table."),
    ],
    "design-creativity": [
        ("2026 UI/UX Trends Worth Watching", "A closer look at the shifts shaping product design."),
        ("Color Psychology in Product Design", "How color choices quietly shape user trust."),
        (
            "Typography Basics Every Designer Should Know",
            "Type is 90% of interface design — here's why.",
        ),
        (
            "Designing for Accessibility From Day One",
            "Why retrofitting accessibility always costs more.",
        ),
        (
            "From Sketch to Prototype: My Process",
            "A practical walkthrough of an early-stage design workflow.",
        ),
        (
            "The Difference Between Good and Great Portfolios",
            "What actually gets a design portfolio noticed.",
        ),
        (
            "Motion Design Principles for Beginners",
            "Micro-interactions that make interfaces feel alive.",
        ),
        (
            "Building a Design System From Scratch",
            "Lessons from setting one up for a five-person team.",
        ),
    ],
    "learning-tips": [
        (
            "The Pomodoro Technique, Revisited",
            "Why 25-minute sprints still work for deep study sessions.",
        ),
        ("How Spaced Repetition Actually Works", "The science behind remembering what you study."),
        ("Study Smarter, Not Longer", "Evidence-based methods that beat cramming every time."),
        ("Building a Study Routine That Sticks", "Habits that survive busy weeks."),
        (
            "Note-Taking Methods Compared",
            "Cornell, outline, and mind maps — which fits your brain?",
        ),
        (
            "Overcoming Procrastination in Online Courses",
            "Practical fixes for the self-paced learning trap.",
        ),
        (
            "How to Learn From Video Courses Effectively",
            "Active watching techniques that actually retain information.",
        ),
        ("Setting Realistic Learning Goals", "Why smaller milestones beat one big deadline."),
    ],
    "industry-insights": [
        (
            "What's Changing in Tech Hiring This Year",
            "A look at how hiring bars are shifting across the industry.",
        ),
        (
            "Remote Work: Where the Industry Stands Now",
            "What companies are actually doing after the hybrid experiments.",
        ),
        (
            "The Rise of the Fractional Specialist",
            "Why more professionals are working across multiple companies.",
        ),
        (
            "How Startups Are Rethinking Junior Hiring",
            "Entry-level roles are changing shape — here's how.",
        ),
        (
            "Industry Certifications: Worth It or Not?",
            "A practical breakdown of which credentials actually matter.",
        ),
        ("What Employers Wish Candidates Knew", "Common gaps between expectations and reality."),
        (
            "The Shift Toward Skills-Based Hiring",
            "Degrees are losing ground to demonstrated ability.",
        ),
        (
            "Freelance Platforms in 2026: A Landscape Overview",
            "Where independent professionals are finding steady work.",
        ),
    ],
    "technology": [
        ("AI Tools Every Professional Should Try", "A curated list beyond the obvious chatbots."),
        (
            "How Large Language Models Are Changing Workflows",
            "Practical use cases beyond the hype.",
        ),
        (
            "A Beginner's Guide to Automation Tools",
            "Save hours a week without writing a line of code.",
        ),
        ("Understanding APIs Without the Jargon", "A plain-language explainer for non-engineers."),
        (
            "The Tools Powering Modern Remote Teams",
            "What actually keeps distributed teams in sync.",
        ),
        (
            "No-Code vs Low-Code: What's the Difference?",
            "Choosing the right approach for your next project.",
        ),
        (
            "Cybersecurity Basics for Everyday Users",
            "Simple habits that prevent most common breaches.",
        ),
        ("How Cloud Computing Actually Works", "A gentle introduction for non-technical readers."),
    ],
    "productivity": [
        (
            "Time-Blocking for People Who Hate Schedules",
            "A flexible system that still gets things done.",
        ),
        ("The Two-Minute Rule and Why It Works", "A tiny habit that clears mental clutter fast."),
        (
            "Building a Second Brain With Simple Tools",
            "Capture, organize, and actually use your notes.",
        ),
        ("How to Run a Meeting That Doesn't Waste Time", "A short framework for sharper meetings."),
        (
            "Digital Minimalism for Busy Professionals",
            "Cutting the noise without cutting the tools you need.",
        ),
        ("The Real Cost of Multitasking", "Why switching tasks is slower than it feels."),
        (
            "Designing a Morning Routine That Sticks",
            "Small, sustainable changes beat dramatic overhauls.",
        ),
        ("Inbox Zero Without the Stress", "A calmer approach to email management."),
    ],
    "community": [
        (
            "Behind the Scenes: How Our Platform Picks Courses",
            "A look at the curation process from the team.",
        ),
        ("Meet the Mentors: Spring Cohort", "Introducing the instructors joining this term."),
        ("Community Spotlight: Student Projects We Loved", "Standout work from recent graduates."),
        ("Recap: Our First Virtual Meetup", "Highlights, feedback, and what's next."),
        ("How to Get Featured on Our Blog", "A quick guide for teachers and contributors."),
        ("Ask Us Anything: Platform Roadmap", "Answers to the most common questions from users."),
        ("Celebrating 1,000 Certificates Issued", "A milestone update from the whole team."),
        (
            "New Feature Rollout: What's Coming Next",
            "A preview of what we're building this quarter.",
        ),
    ],
}

# Real first-person narratives for Student Stories, keyed by slugify(name), everything else
# in the category uses LOREM, but these are meant to read as actual student journeys.
STUDENT_STORY_BODIES: dict[str, list[str]] = {
    "priya-sharma": [
        "I spent five years writing campaign briefs before I admitted I was more interested in why people clicked than what made them click. Marketing gave me a front-row seat to user behavior, but I never got to shape the experience itself.",
        "I enrolled in a part-time UX course while still working full-time, sketching wireframes during my lunch break and testing prototypes on coworkers who had no idea they were my first users. The hardest part wasn't the software — it was unlearning the instinct to sell and learning to listen instead.",
        "Six months after finishing the program, I landed a junior UX role at a fintech startup. My manager still jokes that I'm the only designer on the team who can also write the launch copy. Turns out the pivot wasn't a departure from marketing — it was a deeper way into it.",
    ],
    "daniel-kim": [
        "Everyone told me I needed a CS degree to get hired as a developer. I didn't have one, and going back to school for four years wasn't an option, so I built my own roadmap instead: two structured courses, one real project a month, and a public GitHub profile I updated every week.",
        "The rejections came fast — eleven of them before my first interview. What changed things was building a small tool that solved an actual problem for a local business, not another to-do app. It gave me something real to talk about instead of tutorials I'd copied.",
        "I got my offer as a junior developer eight months after writing my first line of code. I still don't have a degree. I have a portfolio, a habit of shipping, and proof that the roadmap works if you follow it long enough to matter.",
    ],
    "sofia-martinez": [
        "I was thirty-five when I decided to learn to code, and every voice in my head told me I'd missed the window. I had a mortgage, a full-time job in retail management, and exactly zero hours of free time to spare.",
        "I started with fifteen minutes before work and thirty minutes before bed. It was slow. Some weeks I only finished one lesson. But slow was still forward, and after a year of showing up in small pieces, the fundamentals finally clicked.",
        "I'm two years in now, working as a backend developer at a logistics company. My advice to anyone who thinks they've started too late: the only real deadline is the one you set for yourself, and mine turned out to be fifteen minutes a day.",
    ],
    "olena-petrenko": [
        "I finished my coding bootcamp with more anxiety than confidence. My first week on the job, I was convinced everyone could tell I'd only been writing code for four months.",
        'What got me through wasn\'t talent — it was asking questions out loud instead of pretending I understood, and volunteering for the parts of projects nobody else wanted. Slowly, "the new bootcamp grad" became "the person who actually knows how this feature works."',
        "Two years later, I'm leading the same team I once felt intimidated by. I still remember what it's like to not know the answer, and I think that's exactly why I'm good at helping the next junior developer find it.",
    ],
    "marcus-bailey": [
        "I spent six years in corporate finance building the same quarterly reports, and somewhere along the way I realized the part I actually enjoyed wasn't the finance — it was finding the story hidden inside the numbers.",
        "I started teaching myself SQL and data visualization on weekends, using our own company's sales data as practice. When I built a dashboard that caught a pricing error nobody else had noticed, my manager asked who'd made it, and I got my first real chance to move into analytics.",
        "I now build dashboards for a living instead of spreadsheets nobody reads twice. The finance background didn't go to waste — it's why I know which numbers actually matter to the people asking for them.",
    ],
    "aiden-walsh": [
        'I took my first freelance web design client six weeks after finishing my course, thrilled to finally get paid for something I loved. I didn\'t have a contract, I quoted a flat fee for "a few small changes," and I found out the hard way what an open-ended scope really costs.',
        "The project took three times longer than planned and I made almost nothing per hour by the end. But I also learned exactly what I needed for the next client: a written scope, a revision limit, and the confidence to say a request was outside the original agreement.",
        "That rough first project is the reason my business has actual contracts today. I don't look back on it as a failure — it was the most expensive, most useful lesson of my freelance career, and I only had to pay for it once.",
    ],
    "grace-okafor": [
        "I was working full-time when I decided to study data analytics, and for the first month I tried to squeeze lessons in wherever I could find a spare half hour. It didn't work — I was tired, distracted, and quietly giving up.",
        "What changed everything was time-blocking two fixed hours every morning before work, and saying no to almost everything else for those months: fewer social plans, fewer late nights, one clear priority. It wasn't glamorous, but it was sustainable.",
        "I finished the program without burning out, which surprised me more than passing the final project did. The lesson that stuck with me: motivation gets you started, but a schedule you can actually keep is what gets you to the end.",
    ],
    "liam-anderson": [
        "Every job posting wanted a portfolio full of client work I didn't have. So instead of waiting for permission, I gave myself three fake briefs and built them like they were real: a rebrand for a coffee shop that didn't exist, an app redesign for a service I used every day, and a case study breaking down my own design decisions.",
        "I treated each one like a real project — user research, iterations, a written process, not just polished final screens. Recruiters told me later that the process pages were what made them stop scrolling, not the visuals.",
        "Those three self-initiated projects got me my first design interview, and eventually my first job. I didn't need real clients to prove I could do the work. I just needed to prove it to myself first, and let the portfolio show the rest.",
    ],
}


class Command(BaseCommand):
    help = "Seed 8 demo blog articles per category (idempotent, random authors from existing staff/teachers)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cover-image",
            type=Path,
            help="Optional image copied into every seeded article that has no cover yet.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        cover_image_path = options.get("cover_image")
        if cover_image_path and not cover_image_path.is_file():
            raise CommandError(f"Cover image not found: {cover_image_path}")

        authors = list(
            User.objects.filter(
                role__in=[
                    User.RoleChoices.TEACHER,
                    User.RoleChoices.MODERATOR,
                    User.RoleChoices.ADMINISTRATOR,
                ],
            ),
        )
        if not authors:
            raise CommandError(
                "No teacher/moderator/administrator users found. Run `python manage.py seed` first.",
            )

        categories = list(BlogCategory.objects.all())
        if not categories:
            raise CommandError(
                "No blog categories found. Run `python manage.py migrate blog` first."
            )

        created_count = 0
        covers_assigned = 0
        now = timezone.now()

        for category in categories:
            topics = BLOG_TOPICS.get(category.slug, [])
            for title, subtitle in topics:
                slug = slugify(title)
                author = random.choice(authors)
                story_paragraphs = STUDENT_STORY_BODIES.get(slug)
                if story_paragraphs:
                    body_html = "".join(f"<p>{p}</p>" for p in story_paragraphs)
                else:
                    body_html = f"<p>{random.choice(LOREM)}</p><p>{random.choice(LOREM)}</p>"
                published_at = now - timezone.timedelta(days=random.randint(1, 120))
                article, created = Article.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "title": title,
                        "subtitle": subtitle,
                        "body_html": body_html,
                        "category": category,
                        "author": author,
                        "status": Article.StatusChoices.PUBLISHED,
                        "published_at": published_at,
                    },
                )
                if created:
                    created_count += 1
                if cover_image_path and not article.cover_image:
                    with cover_image_path.open("rb") as image_file:
                        article.cover_image.save(
                            cover_image_path.name,
                            File(image_file),
                            save=True,
                        )
                    covers_assigned += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_count} new articles, assigned {covers_assigned} covers "
                f"({Article.objects.count()} total).",
            )
        )
