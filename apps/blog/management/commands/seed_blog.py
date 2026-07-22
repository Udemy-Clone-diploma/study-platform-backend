"""Seed the database with demo blog articles, 8 per category, with randomly assigned authors.

Idempotent: articles are created with get_or_create on their slug, so running it
repeatedly will not duplicate rows.

    python manage.py seed_blog

Requires at least one teacher/moderator/administrator user to already exist
(e.g. via `python manage.py seed`) -- authors are picked at random from them.
"""

import random

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
    "student-stories": [
        ("From Marketing to UX: My Career Pivot", "How switching fields after five years led to a design role I love."),
        ("How I Landed My First Junior Developer Job", "No CS degree, no problem — here's the roadmap that worked for me."),
        ("Teaching Myself to Code at 35", "It's never too late to start a new career in tech."),
        ("From Bootcamp Graduate to Team Lead in Two Years", "Lessons learned scaling from junior to leading a small team."),
        ("Why I Left Finance for Data Analytics", "Spreadsheets got me hooked on numbers — now I build dashboards for a living."),
        ("My First Freelance Client (and What Went Wrong)", "Mistakes I made so you don't have to."),
        ("Studying While Working Full-Time: What Actually Worked", "Time-blocking, accountability, and saying no to everything else."),
        ("Building a Portfolio With Zero Experience", "Three side projects that got me hired."),
    ],
    "career-growth": [
        ("Negotiating Your First Raise", "A practical script for a conversation most people avoid."),
        ("How to Ask for a Promotion Without Feeling Awkward", "Framing your case around impact, not tenure."),
        ("Freelancing 101: Setting Rates You Won't Regret", "Pricing strategies for new freelancers."),
        ("Building a Personal Brand as a Developer", "Why writing in public pays off long-term."),
        ("The Skills Gap Nobody Talks About", "Soft skills that matter as much as your stack."),
        ("Switching Specializations Mid-Career", "How to reposition your experience for a new niche."),
        ("Networking for Introverts", "Low-pressure ways to build real professional relationships."),
        ("What Recruiters Actually Look For", "Insights from the other side of the hiring table."),
    ],
    "design-creativity": [
        ("2026 UI/UX Trends Worth Watching", "A closer look at the shifts shaping product design."),
        ("Color Psychology in Product Design", "How color choices quietly shape user trust."),
        ("Typography Basics Every Designer Should Know", "Type is 90% of interface design — here's why."),
        ("Designing for Accessibility From Day One", "Why retrofitting accessibility always costs more."),
        ("From Sketch to Prototype: My Process", "A practical walkthrough of an early-stage design workflow."),
        ("The Difference Between Good and Great Portfolios", "What actually gets a design portfolio noticed."),
        ("Motion Design Principles for Beginners", "Micro-interactions that make interfaces feel alive."),
        ("Building a Design System From Scratch", "Lessons from setting one up for a five-person team."),
    ],
    "learning-tips": [
        ("The Pomodoro Technique, Revisited", "Why 25-minute sprints still work for deep study sessions."),
        ("How Spaced Repetition Actually Works", "The science behind remembering what you study."),
        ("Study Smarter, Not Longer", "Evidence-based methods that beat cramming every time."),
        ("Building a Study Routine That Sticks", "Habits that survive busy weeks."),
        ("Note-Taking Methods Compared", "Cornell, outline, and mind maps — which fits your brain?"),
        ("Overcoming Procrastination in Online Courses", "Practical fixes for the self-paced learning trap."),
        ("How to Learn From Video Courses Effectively", "Active watching techniques that actually retain information."),
        ("Setting Realistic Learning Goals", "Why smaller milestones beat one big deadline."),
    ],
    "industry-insights": [
        ("What's Changing in Tech Hiring This Year", "A look at how hiring bars are shifting across the industry."),
        ("Remote Work: Where the Industry Stands Now", "What companies are actually doing after the hybrid experiments."),
        ("The Rise of the Fractional Specialist", "Why more professionals are working across multiple companies."),
        ("How Startups Are Rethinking Junior Hiring", "Entry-level roles are changing shape — here's how."),
        ("Industry Certifications: Worth It or Not?", "A practical breakdown of which credentials actually matter."),
        ("What Employers Wish Candidates Knew", "Common gaps between expectations and reality."),
        ("The Shift Toward Skills-Based Hiring", "Degrees are losing ground to demonstrated ability."),
        ("Freelance Platforms in 2026: A Landscape Overview", "Where independent professionals are finding steady work."),
    ],
    "technology": [
        ("AI Tools Every Professional Should Try", "A curated list beyond the obvious chatbots."),
        ("How Large Language Models Are Changing Workflows", "Practical use cases beyond the hype."),
        ("A Beginner's Guide to Automation Tools", "Save hours a week without writing a line of code."),
        ("Understanding APIs Without the Jargon", "A plain-language explainer for non-engineers."),
        ("The Tools Powering Modern Remote Teams", "What actually keeps distributed teams in sync."),
        ("No-Code vs Low-Code: What's the Difference?", "Choosing the right approach for your next project."),
        ("Cybersecurity Basics for Everyday Users", "Simple habits that prevent most common breaches."),
        ("How Cloud Computing Actually Works", "A gentle introduction for non-technical readers."),
    ],
    "productivity": [
        ("Time-Blocking for People Who Hate Schedules", "A flexible system that still gets things done."),
        ("The Two-Minute Rule and Why It Works", "A tiny habit that clears mental clutter fast."),
        ("Building a Second Brain With Simple Tools", "Capture, organize, and actually use your notes."),
        ("How to Run a Meeting That Doesn't Waste Time", "A short framework for sharper meetings."),
        ("Digital Minimalism for Busy Professionals", "Cutting the noise without cutting the tools you need."),
        ("The Real Cost of Multitasking", "Why switching tasks is slower than it feels."),
        ("Designing a Morning Routine That Sticks", "Small, sustainable changes beat dramatic overhauls."),
        ("Inbox Zero Without the Stress", "A calmer approach to email management."),
    ],
    "community": [
        ("Behind the Scenes: How Our Platform Picks Courses", "A look at the curation process from the team."),
        ("Meet the Mentors: Spring Cohort", "Introducing the instructors joining this term."),
        ("Community Spotlight: Student Projects We Loved", "Standout work from recent graduates."),
        ("Recap: Our First Virtual Meetup", "Highlights, feedback, and what's next."),
        ("How to Get Featured on Our Blog", "A quick guide for teachers and contributors."),
        ("Ask Us Anything: Platform Roadmap", "Answers to the most common questions from users."),
        ("Celebrating 1,000 Certificates Issued", "A milestone update from the whole team."),
        ("New Feature Rollout: What's Coming Next", "A preview of what we're building this quarter."),
    ],
}


class Command(BaseCommand):
    help = "Seed 8 demo blog articles per category (idempotent, random authors from existing staff/teachers)."

    @transaction.atomic
    def handle(self, *args, **options):
        authors = list(
            User.objects.filter(
                role__in=[User.RoleChoices.TEACHER, User.RoleChoices.MODERATOR, User.RoleChoices.ADMINISTRATOR],
            ),
        )
        if not authors:
            raise CommandError(
                "No teacher/moderator/administrator users found. Run `python manage.py seed` first.",
            )

        categories = list(BlogCategory.objects.all())
        if not categories:
            raise CommandError("No blog categories found. Run `python manage.py migrate blog` first.")

        created_count = 0
        now = timezone.now()

        for category in categories:
            topics = BLOG_TOPICS.get(category.slug, [])
            for i, (title, subtitle) in enumerate(topics):
                slug = slugify(title)
                author = random.choice(authors)
                body_html = f"<p>{random.choice(LOREM)}</p><p>{random.choice(LOREM)}</p>"
                published_at = now - timezone.timedelta(days=random.randint(1, 120))
                _, created = Article.objects.get_or_create(
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

        self.stdout.write(self.style.SUCCESS(
            f"Done. Created {created_count} new articles ({Article.objects.count()} total).",
        ))
