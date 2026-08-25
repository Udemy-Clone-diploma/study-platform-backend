"""Demo accounts.

Addresses are firstname.lastname@example.com. The local part is realistic so the
admin user table does not read as generated; the domain stays example.com, which
RFC 2606 reserves for exactly this and which therefore never delivers mail. That
matters because the deployed backend sends real email (moderation warnings,
teacher invitations), and a plausible-looking gmail.com address may well belong
to somebody.

The email is the natural key the seeder looks rows up by, so renaming an account
here creates a new one rather than updating the old.
"""

ADMIN = {
    "email": "diana.whitfield@example.com",
    "first_name": "Diana",
    "last_name": "Whitfield",
    "linkedin": "https://linkedin.com/in/diana-whitfield",
}

MODERATORS = [
    {
        "email": "marcus.feldman@example.com",
        "first_name": "Marcus",
        "last_name": "Feldman",
        "level": "senior",
    },
    {
        "email": "priya.raman@example.com",
        "first_name": "Priya",
        "last_name": "Raman",
        "level": "junior",
    },
]

TEACHERS = [
    {
        "email": "andrii.melnyk@example.com",
        "first_name": "Andrii",
        "last_name": "Melnyk",
        "specialization": "Backend Engineering",
        "experience": "11 years building Django and FastAPI services for fintech and logistics.",
        "bio": (
            "I have spent most of my career on the unglamorous half of the stack: schemas that "
            "survive a migration, queries that stay fast at ten million rows, and deploys nobody "
            "has to babysit. I teach the way I wish I had been taught, by building one real "
            "service end to end instead of forty disconnected snippets."
        ),
        "rating": "4.80",
        "linkedin": "https://linkedin.com/in/andrii-melnyk",
        "instagram": "https://instagram.com/melnyk.codes",
    },
    {
        "email": "sofia.lindqvist@example.com",
        "first_name": "Sofia",
        "last_name": "Lindqvist",
        "specialization": "Frontend Development",
        "experience": "9 years in product teams, previously frontend lead at a design agency.",
        "bio": (
            "I care about interfaces that feel obvious. Most of that comes down to state you can "
            "reason about and components small enough to hold in your head. My courses are heavy "
            "on refactoring: we write the naive version first, then fix it together."
        ),
        "rating": "4.60",
        "linkedin": "https://linkedin.com/in/sofia-lindqvist",
        "instagram": "https://instagram.com/sofia.builds",
    },
    {
        "email": "daniel.okonkwo@example.com",
        "first_name": "Daniel",
        "last_name": "Okonkwo",
        "specialization": "Product Design",
        "experience": "12 years in product design, mentor to 200+ designers in their first role.",
        "bio": (
            "Design is a research problem before it is a drawing problem. I teach people to talk "
            "to users without leading them, to turn messy interview notes into decisions, and to "
            "defend those decisions with something better than personal taste."
        ),
        "rating": "4.90",
        "linkedin": "https://linkedin.com/in/daniel-okonkwo",
        "instagram": "https://instagram.com/okonkwo.design",
    },
    {
        # Created from an approved teacher application: invited, not yet activated.
        "email": "elena.ruiz@example.com",
        "first_name": "Elena",
        "last_name": "Ruiz",
        "specialization": "Data Engineering",
        "experience": "8 years building analytics pipelines in retail.",
        "bio": "Analytics engineer turned instructor. Joins the platform next term.",
        "rating": "0.00",
        "status": "inactive",
        "is_email_verified": False,
    },
]

STUDENTS = [
    {
        "email": "kateryna.bondar@example.com",
        "first_name": "Kateryna",
        "last_name": "Bondar",
        "learning_goals": "Land a first job as a backend developer within a year.",
        "education_level": "High school",
        "date_of_birth": "2001-04-12",
    },
    {
        "email": "tomasz.wisniewski@example.com",
        "first_name": "Tomasz",
        "last_name": "Wisniewski",
        "learning_goals": "Switch careers from marketing into UX research.",
        "education_level": "Bachelor's",
        "date_of_birth": "1994-09-30",
    },
    {
        "email": "aisha.rahman@example.com",
        "first_name": "Aisha",
        "last_name": "Rahman",
        "learning_goals": "Add practical project work on top of a CS degree.",
        "education_level": "Bachelor's (in progress)",
        "date_of_birth": "2003-01-22",
    },
    {
        "email": "lukas.berger@example.com",
        "first_name": "Lukas",
        "last_name": "Berger",
        "learning_goals": "Fill the gaps left by three years of self-teaching.",
        "education_level": "Self-taught",
        "date_of_birth": "1998-07-05",
    },
    {
        "email": "mariya.ivanenko@example.com",
        "first_name": "Mariya",
        "last_name": "Ivanenko",
        "learning_goals": "Move from data analysis into data engineering.",
        "education_level": "Master's",
        "date_of_birth": "1992-11-17",
    },
    {
        "email": "noah.callahan@example.com",
        "first_name": "Noah",
        "last_name": "Callahan",
        "learning_goals": "Explore design and code as a serious hobby.",
        "education_level": "Some college",
        "date_of_birth": "2000-02-28",
    },
    {
        "email": "viktor.sokolov@example.com",
        "first_name": "Viktor",
        "last_name": "Sokolov",
        "learning_goals": "Prepare for a junior developer interview.",
        "education_level": "Vocational",
        "date_of_birth": "1999-06-14",
        # Blocked as the resolution of a harassment report (see moderation.py).
        "is_blocked": True,
        "status": "inactive",
    },
    {
        "email": "hanna.petrova@example.com",
        "first_name": "Hanna",
        "last_name": "Petrova",
        "learning_goals": "Learn enough SQL to own reporting at work.",
        "education_level": "Bachelor's",
        "date_of_birth": "1996-03-08",
        # Soft-deleted account, so the admin user table has a restore case.
        "is_deleted": True,
        "status": "inactive",
    },
    {
        "email": "ibrahim.toure@example.com",
        "first_name": "Ibrahim",
        "last_name": "Toure",
        "learning_goals": "Build a portfolio of small data projects.",
        "education_level": "Bachelor's",
        "date_of_birth": "1997-12-02",
    },
    {
        "email": "julia.novak@example.com",
        "first_name": "Julia",
        "last_name": "Novak",
        "learning_goals": "Move from QA into frontend development.",
        "education_level": "Bachelor's",
        "date_of_birth": "1995-05-21",
    },
]
