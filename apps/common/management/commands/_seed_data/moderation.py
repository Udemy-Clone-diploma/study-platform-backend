"""Moderation, chat, and homework demo data.

Everything here is referenced by email or slug so the seed command can resolve
rows it created earlier without threading objects through the data.

`days_ago` values are what put rows inside the moderator dashboard's 7-day and
14-day comparison windows. An action must never be older than the report it
belongs to (a larger `days_ago` than its report) or the dashboard's average
review time collapses to zero.
"""

ADMIN_NOTES = [
    {
        "user": "sofia.lindqvist@example.com",
        "content": (
            "Asked twice for an invoice address change in the middle of a payout cycle. "
            "Handled manually both times; point at the finance form next time."
        ),
        "days_ago": 26,
    },
    {
        "user": "viktor.sokolov@example.com",
        "content": (
            "Blocked after a harassment report in the React cohort chat. Two prior warnings "
            "on file. Do not lift the block without a written apology to the reporter."
        ),
        "days_ago": 9,
    },
    {
        "user": "ibrahim.toure@example.com",
        "content": (
            "Block was reversed: the reported messages turned out to be quoted from someone "
            "else. Apologised to the student by email on our side."
        ),
        "days_ago": 5,
    },
    {
        "user": "elena.ruiz@example.com",
        "content": "Invited after her application was approved. Has not activated the account yet.",
        "days_ago": 12,
    },
]

# Each entry becomes one UserReport plus its immutable action chain.
USER_REPORTS = [
    # --- Open, unassigned -------------------------------------------------
    {
        "key": "spam-noah-1",
        "reported": "noah.callahan@example.com",
        "reporter": "kateryna.bondar@example.com",
        "reason": "spam",
        "details": "Posting the same paid bootcamp link under every lesson discussion.",
        "status": "pending",
        "created_days_ago": 3,
        "actions": [],
    },
    {
        "key": "profile-ibrahim-1",
        "reported": "ibrahim.toure@example.com",
        "reporter": "tomasz.wisniewski@example.com",
        "reason": "inappropriate_profile",
        "details": "Profile bio contains a phone number and an offer to sell course material access.",
        "status": "pending",
        "created_days_ago": 2,
        "actions": [],
    },
    {
        "key": "other-julia-1",
        "reported": "julia.novak@example.com",
        "reporter": "aisha.rahman@example.com",
        "reason": "other",
        "details": "Keeps posting exam answers in the group chat before the deadline.",
        "status": "pending",
        "created_days_ago": 1,
        "actions": [],
    },
    # --- Claimed, in review ----------------------------------------------
    {
        "key": "harassment-noah-1",
        "reported": "noah.callahan@example.com",
        "reporter": "lukas.berger@example.com",
        "reason": "harassment",
        "details": "Repeated personal remarks about my accent during the live session chat.",
        "status": "in_review",
        "moderator": "marcus.feldman@example.com",
        "assigned_days_ago": 4,
        "created_days_ago": 6,
        "actions": [
            {
                "action": "claimed",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "pending",
                "new": "in_review",
                "days_ago": 4,
                "note": "Pulling the session transcript before deciding.",
            },
        ],
    },
    {
        "key": "fraud-ibrahim-1",
        "reported": "ibrahim.toure@example.com",
        "reporter": "mariya.ivanenko@example.com",
        "reason": "fraud",
        "details": "Offered to sell me his account login for the paid cohort.",
        "status": "in_review",
        "moderator": "marcus.feldman@example.com",
        "assigned_days_ago": 2,
        "created_days_ago": 5,
        "actions": [
            {
                "action": "claimed",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "pending",
                "new": "in_review",
                "days_ago": 2,
                "note": "",
            },
        ],
    },
    {
        "key": "spam-julia-1",
        "reported": "julia.novak@example.com",
        "reporter": "noah.callahan@example.com",
        "reason": "spam",
        "details": "Unsolicited direct messages advertising a competing course.",
        "status": "in_review",
        "moderator": "priya.raman@example.com",
        "assigned_days_ago": 6,
        "created_days_ago": 8,
        "actions": [
            {
                "action": "claimed",
                "actor": "priya.raman@example.com",
                "role": "moderator",
                "previous": "pending",
                "new": "in_review",
                "days_ago": 6,
                "note": "",
            },
        ],
    },
    # --- Escalated (target is staff, so it goes straight to an admin) ------
    {
        "key": "escalated-moderator-1",
        "reported": "priya.raman@example.com",
        "reporter": "kateryna.bondar@example.com",
        "reason": "other",
        "details": "The moderator removed my review without explaining which rule it broke.",
        "status": "escalated",
        "created_days_ago": 7,
        "escalated_days_ago": 7,
        "escalation_note": "Auto-escalated: the reported account is a staff member.",
        "actions": [
            {
                "action": "escalated",
                "actor": None,
                "role": "system",
                "previous": "pending",
                "new": "escalated",
                "days_ago": 7,
                "note": "Auto-escalated: the reported account is a staff member.",
            },
        ],
    },
    {
        "key": "escalated-admin-1",
        "reported": "diana.whitfield@example.com",
        "reporter": "tomasz.wisniewski@example.com",
        "reason": "impersonation",
        "details": "Someone emailed me claiming to be platform support and asked for my password.",
        "status": "escalated",
        "created_days_ago": 11,
        "escalated_days_ago": 10,
        "escalated_by": "marcus.feldman@example.com",
        "escalation_note": "Phishing attempt using our brand. Needs an admin decision on the notice.",
        "actions": [
            {
                "action": "claimed",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "pending",
                "new": "in_review",
                "days_ago": 11,
                "note": "",
            },
            {
                "action": "escalated",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "in_review",
                "new": "escalated",
                "days_ago": 10,
                "note": "Not a platform account issue, this needs a security notice.",
            },
        ],
    },
    {
        "key": "escalated-moderator-2",
        "reported": "marcus.feldman@example.com",
        "reporter": "lukas.berger@example.com",
        "reason": "other",
        "details": "Closed my report in four minutes without asking me anything.",
        "status": "escalated",
        "created_days_ago": 4,
        "escalated_days_ago": 4,
        "escalation_note": "Auto-escalated: the reported account is a staff member.",
        "actions": [
            {
                "action": "escalated",
                "actor": None,
                "role": "system",
                "previous": "pending",
                "new": "escalated",
                "days_ago": 4,
                "note": "Auto-escalated: the reported account is a staff member.",
            },
        ],
    },
    # --- Resolved ---------------------------------------------------------
    {
        "key": "warning-noah-1",
        "reported": "noah.callahan@example.com",
        "reporter": "tomasz.wisniewski@example.com",
        "reason": "spam",
        "details": "Third time posting an affiliate link in the cohort chat.",
        "status": "resolved",
        "resolution": "warning",
        "moderator": "marcus.feldman@example.com",
        "assigned_days_ago": 12,
        "created_days_ago": 13,
        "resolved_by": "marcus.feldman@example.com",
        "resolved_days_ago": 12,
        "resolution_note": "Formal warning sent. Links removed from the three affected threads.",
        "actions": [
            {
                "action": "claimed",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "pending",
                "new": "in_review",
                "days_ago": 12,
                "note": "",
            },
            {
                "action": "warning",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "in_review",
                "new": "resolved",
                "days_ago": 12,
                "note": "Formal warning sent. Links removed from the three affected threads.",
            },
        ],
    },
    {
        "key": "warning-julia-1",
        "reported": "julia.novak@example.com",
        "reporter": "lukas.berger@example.com",
        "reason": "other",
        "details": "Shared a recording of the live session outside the cohort.",
        "status": "resolved",
        "resolution": "warning",
        "moderator": "priya.raman@example.com",
        "assigned_days_ago": 9,
        "created_days_ago": 10,
        "resolved_by": "priya.raman@example.com",
        "resolved_days_ago": 9,
        "resolution_note": "Warned. Recording taken down within the hour, no further action.",
        "actions": [
            {
                "action": "claimed",
                "actor": "priya.raman@example.com",
                "role": "moderator",
                "previous": "pending",
                "new": "in_review",
                "days_ago": 9,
                "note": "",
            },
            {
                "action": "warning",
                "actor": "priya.raman@example.com",
                "role": "moderator",
                "previous": "in_review",
                "new": "resolved",
                "days_ago": 9,
                "note": "Warned. Recording taken down within the hour.",
            },
        ],
    },
    {
        "key": "blocked-viktor-1",
        "reported": "viktor.sokolov@example.com",
        "reporter": "aisha.rahman@example.com",
        "reason": "harassment",
        "details": "Sustained personal attacks in direct messages after I asked him to stop.",
        "status": "resolved",
        "resolution": "blocked",
        "moderator": "marcus.feldman@example.com",
        "assigned_days_ago": 10,
        "created_days_ago": 11,
        "resolved_by": "marcus.feldman@example.com",
        "resolved_days_ago": 9,
        "resolution_note": "Account blocked. Two prior warnings on file, pattern is clear.",
        "blocks_user": True,
        "actions": [
            {
                "action": "claimed",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "pending",
                "new": "in_review",
                "days_ago": 10,
                "note": "",
            },
            {
                "action": "blocked",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "in_review",
                "new": "resolved",
                "days_ago": 9,
                "note": "Blocked after reviewing the message history.",
            },
        ],
    },
    {
        "key": "unblocked-ibrahim-1",
        "reported": "ibrahim.toure@example.com",
        "reporter": "kateryna.bondar@example.com",
        "reason": "hate",
        "details": "Offensive language in the data bootcamp chat.",
        "status": "resolved",
        "resolution": "unblocked",
        "moderator": "marcus.feldman@example.com",
        "assigned_days_ago": 8,
        "created_days_ago": 8,
        "resolved_by": "marcus.feldman@example.com",
        "resolved_days_ago": 5,
        "resolution_note": (
            "Block reversed. The messages were quotes from an article he was criticising, "
            "which the report screenshot cut off."
        ),
        "actions": [
            {
                "action": "claimed",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "pending",
                "new": "in_review",
                "days_ago": 8,
                "note": "",
            },
            {
                "action": "blocked",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "in_review",
                "new": "resolved",
                "days_ago": 7,
                "note": "Blocked pending a full read of the thread.",
            },
            {
                "action": "unblocked",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "resolved",
                "new": "resolved",
                "days_ago": 5,
                "note": "Reversed after reading the full thread. Quoted text, not his own.",
            },
        ],
    },
    {
        "key": "dismissed-kateryna-1",
        "reported": "kateryna.bondar@example.com",
        "reporter": "julia.novak@example.com",
        "reason": "other",
        "details": "She disagreed with my answer in the forum.",
        "status": "resolved",
        "resolution": "dismissed",
        "moderator": "priya.raman@example.com",
        "assigned_days_ago": 6,
        "created_days_ago": 6,
        "resolved_by": "priya.raman@example.com",
        "resolved_days_ago": 6,
        "resolution_note": "No rule broken. Disagreement is not harassment.",
        "actions": [
            {
                "action": "claimed",
                "actor": "priya.raman@example.com",
                "role": "moderator",
                "previous": "pending",
                "new": "in_review",
                "days_ago": 6,
                "note": "",
            },
            {
                "action": "dismissed",
                "actor": "priya.raman@example.com",
                "role": "moderator",
                "previous": "in_review",
                "new": "resolved",
                "days_ago": 6,
                "note": "No rule broken.",
            },
        ],
    },
    {
        "key": "dismissed-mariya-1",
        "reported": "mariya.ivanenko@example.com",
        "reporter": "ibrahim.toure@example.com",
        "reason": "spam",
        "details": "Posted her portfolio link in the introductions thread.",
        "status": "resolved",
        "resolution": "dismissed",
        "moderator": "marcus.feldman@example.com",
        "assigned_days_ago": 13,
        "created_days_ago": 14,
        "resolved_by": "marcus.feldman@example.com",
        "resolved_days_ago": 13,
        "resolution_note": "The introductions thread explicitly invites portfolio links.",
        "actions": [
            {
                "action": "claimed",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "pending",
                "new": "in_review",
                "days_ago": 13,
                "note": "",
            },
            {
                "action": "dismissed",
                "actor": "marcus.feldman@example.com",
                "role": "moderator",
                "previous": "in_review",
                "new": "resolved",
                "days_ago": 13,
                "note": "Working as intended.",
            },
        ],
    },
]

TEACHER_APPLICATIONS = [
    {
        "email": "marta.kowal@example.com",
        "first_name": "Marta",
        "last_name": "Kowal",
        "date_of_birth": "1990-08-19",
        "phone_number": "+48 601 224 118",
        "specialization": "Technical writing",
        "years_experience": 7,
        "experience": "Documentation lead for two developer tools companies.",
        "bio": "I teach engineers to write documentation their colleagues will actually read.",
        "motivation": (
            "Every team I join has the same problem and nobody teaches it. I would like to "
            "run a short, practical course on writing for developers."
        ),
        "directions": ["IT"],
        "linkedin": "https://linkedin.com/in/marta-kowal",
        "status": "pending",
        "submitted_days_ago": 4,
    },
    {
        "email": "sam.ito@example.com",
        "first_name": "Sam",
        "last_name": "Ito",
        "date_of_birth": "1987-02-03",
        "phone_number": "+81 90 4412 9087",
        "specialization": "Motion design",
        "years_experience": 11,
        "experience": "Freelance motion designer, previously in-house at a broadcast studio.",
        "bio": "Motion design for people who already know how to draw but not how to move things.",
        "motivation": "I have taught this as workshops for years and want a proper course format.",
        "directions": ["Design"],
        "instagram": "https://instagram.com/sam.moves",
        "behance": "https://behance.net/samito",
        "status": "pending",
        "submitted_days_ago": 9,
    },
    {
        "email": "elena.ruiz@example.com",
        "first_name": "Elena",
        "last_name": "Ruiz",
        "date_of_birth": "1991-11-27",
        "phone_number": "+34 611 900 244",
        "specialization": "Data Engineering",
        "years_experience": 8,
        "experience": "Eight years building analytics pipelines for a retail group.",
        "bio": "Analytics engineer turned instructor.",
        "motivation": "I want to teach the pipeline work that analytics courses always skip.",
        "directions": ["IT", "Business"],
        "linkedin": "https://linkedin.com/in/elena-ruiz-data",
        "status": "approved",
        "submitted_days_ago": 20,
        "decided_days_ago": 13,
        "moderator": "marcus.feldman@example.com",
        "moderator_comment": "Strong background and a clear course outline. Approved.",
        "creates_user": "elena.ruiz@example.com",
    },
    {
        "email": "pavlo.hrytsenko@example.com",
        "first_name": "Pavlo",
        "last_name": "Hrytsenko",
        "date_of_birth": "1999-05-30",
        "phone_number": "+380 63 118 4420",
        "specialization": "Cryptocurrency trading",
        "years_experience": 1,
        "experience": "One year of personal trading.",
        "bio": "I want to teach people how to make money fast.",
        "motivation": "There is a lot of demand and I can fill it.",
        "directions": ["Business"],
        "status": "cancelled",
        "submitted_days_ago": 17,
        "decided_days_ago": 16,
        "moderator": "priya.raman@example.com",
        "moderator_comment": (
            "Declined. Outside what the platform teaches, and the outline promises returns "
            "we cannot let an instructor advertise."
        ),
    },
    {
        "email": "nadia.brahim@example.com",
        "first_name": "Nadia",
        "last_name": "Brahim",
        "date_of_birth": "1985-01-14",
        "phone_number": "+33 6 88 21 44 07",
        "specialization": "Conversational French",
        "years_experience": 14,
        "experience": "Language school teacher, DELF examiner.",
        "bio": "Fourteen years teaching French to adults who are convinced they are bad at languages.",
        "motivation": "I would like to move my evening classes online and reach more people.",
        "directions": ["Languages"],
        "status": "cancelled",
        "submitted_days_ago": 25,
        "decided_days_ago": 22,
        "moderator": "marcus.feldman@example.com",
        "moderator_comment": (
            "Withdrawn by the applicant before the interview: she took a full-time role. "
            "Told her to reapply in the autumn."
        ),
    },
]

# Reports against reviews. `review` names the (course slug, student email) pair.
REVIEW_REPORTS = [
    {
        "course": "backend-engineering-django",
        "student": "aisha.rahman@example.com",
        "reporters": ["kateryna.bondar@example.com"],
        "reason": "This is a review of the teacher's other course, not this one.",
        "days_ago": 6,
        "moderation_status": "",
    },
    {
        "course": "ux-design-fundamentals",
        "student": "mariya.ivanenko@example.com",
        "reporters": ["tomasz.wisniewski@example.com", "lukas.berger@example.com"],
        "reason": "Contains a discount code for an unrelated site.",
        "days_ago": 5,
        "moderation_status": "",
    },
    {
        "course": "data-analysis-bootcamp",
        "student": "lukas.berger@example.com",
        "reporters": ["ibrahim.toure@example.com"],
        "reason": "Personal remark about the instructor rather than the course.",
        "days_ago": 9,
        "moderation_status": "pending",
        "moderator": "marcus.feldman@example.com",
        "assigned_days_ago": 8,
    },
    {
        "course": "fullstack-javascript",
        "student": "noah.callahan@example.com",
        "reporters": ["julia.novak@example.com"],
        "reason": "Says nothing about the course, just a link.",
        "days_ago": 7,
        "moderation_status": "pending",
        "moderator": "marcus.feldman@example.com",
        "assigned_days_ago": 7,
    },
    {
        "course": "react-from-scratch",
        "student": "tomasz.wisniewski@example.com",
        "reporters": ["noah.callahan@example.com"],
        "reason": "I think this is a fake review.",
        "days_ago": 12,
        "moderation_status": "approved",
        "moderator": "marcus.feldman@example.com",
        "assigned_days_ago": 11,
        "moderated_days_ago": 11,
    },
]

# Extra reviews written only so the moderation queue has rejected examples too.
EXTRA_REVIEWS = [
    {
        "course": "backend-engineering-django",
        "student": "ibrahim.toure@example.com",
        "rating": 1,
        "text": "Get 90% off any course at cheapcourses.example.com with code SAVE90.",
        "days_ago": 14,
        "reporters": ["kateryna.bondar@example.com", "mariya.ivanenko@example.com"],
        "report_reason": "Advertising, not a review.",
        "moderation_status": "rejected",
        "moderator": "marcus.feldman@example.com",
        "assigned_days_ago": 13,
        "moderated_days_ago": 13,
    },
    {
        "course": "data-analysis-bootcamp",
        "student": "julia.novak@example.com",
        "rating": 2,
        "text": "The instructor never replies. Complete waste of money, avoid.",
        "days_ago": 10,
        "reporters": ["mariya.ivanenko@example.com"],
        "report_reason": "Factually wrong, the instructor answered within a day every time.",
        "moderation_status": "rejected",
        "moderator": "priya.raman@example.com",
        "assigned_days_ago": 9,
        "moderated_days_ago": 8,
    },
    {
        "course": "react-from-scratch",
        "student": "julia.novak@example.com",
        "rating": 5,
        "text": "Clear explanations and the refactoring sections were the best part.",
        "days_ago": 16,
        "moderation_status": "approved",
        "moderator": "priya.raman@example.com",
        "assigned_days_ago": 15,
        "moderated_days_ago": 15,
    },
]

# Course moderation history. Each entry drives one approval or rejection record.
COURSE_MODERATION = {
    # Courses approved in the past, so the approval-records screen has history.
    # Approvals land a couple of days after the course was created: the dashboard
    # measures review duration as approved_at minus course.created_at, so a wide
    # gap here shows up as an average review time of several weeks.
    "approvals": [
        {
            "course": "backend-engineering-django",
            "moderator": "marcus.feldman@example.com",
            "days_ago": 128,
        },
        {"course": "react-from-scratch", "moderator": "priya.raman@example.com", "days_ago": 124},
        {
            "course": "ux-design-fundamentals",
            "moderator": "marcus.feldman@example.com",
            "days_ago": 58,
        },
        {
            "course": "data-analysis-bootcamp",
            "moderator": "marcus.feldman@example.com",
            "days_ago": 48,
        },
        {"course": "fullstack-javascript", "moderator": "priya.raman@example.com", "days_ago": 38},
        {"course": "intro-to-devops", "moderator": "marcus.feldman@example.com", "days_ago": 38},
    ],
    # Rejections, in chronological order per course. Only `final: "rejected"`
    # writes a RejectedCourseRecord; anything else returns the course as
    # needs_revision and leaves the moderator's notes on the ModerationReview.
    # `restore_after` replays the teacher pulling it back into a draft.
    "rejections": [
        {
            "course": "advanced-kubernetes",
            "moderator": "priya.raman@example.com",
            "days_ago": 20,
            "final": "rejected",
            "restore_after": True,
            "basics_comment": "Level says advanced but the outline starts from first principles.",
            "content_comment": "The operator module is a single lesson with no exercise.",
            "final_comment": (
                "Rejected as submitted. Decide who this is for: it currently reads as two "
                "different courses stapled together."
            ),
        },
        {
            "course": "sql-for-analysts",
            "moderator": "marcus.feldman@example.com",
            "days_ago": 12,
            "final": "rejected",
            "restore_after": True,
            "basics_comment": "Short description promises more than the outline delivers.",
            "content_comment": "Two modules with no assessment and no practice files.",
            "final_comment": (
                "Rejected. Add at least one exercise set per module and a final assessment, "
                "then open a new draft."
            ),
        },
        {
            "course": "sql-for-analysts",
            "moderator": "marcus.feldman@example.com",
            "days_ago": 5,
            "final": "rejected",
            "basics_comment": "Description unchanged since the last review.",
            "content_comment": "Still no assessments. Nothing was added between submissions.",
            "final_comment": (
                "Rejected again. Resubmitted twice without the changes we asked for; please "
                "talk to us before the next attempt."
            ),
        },
        {
            "course": "photography-basics",
            "moderator": "marcus.feldman@example.com",
            "days_ago": 8,
            "final": "",
            "basics_comment": "Add a syllabus to the description.",
            "content_comment": "At least one lesson must be marked as a free preview.",
            "final_comment": "Close. Add the syllabus and a preview lesson and resubmit.",
        },
    ],
    # A published course with a submitted edit waiting for a moderator.
    "pending_edits": [
        {
            "course": "backend-engineering-django",
            "submitted_days_ago": 2,
            "moderator": None,
            "changes": {
                "subtitle": "From an empty folder to a deployed and monitored REST API",
                "short_description": (
                    "Build a production-grade REST API with Django and DRF, then keep it "
                    "healthy once real users arrive."
                ),
            },
        },
        {
            "course": "data-analysis-bootcamp",
            "submitted_days_ago": 5,
            "moderator": "marcus.feldman@example.com",
            "changes": {
                "subtitle": "From spreadsheets to dashboards, now with a SQL primer",
            },
        },
    ],
}

# Chat rooms and their message scripts. `days_ago` backdates each message.
CHAT_SCRIPTS = [
    {
        "key": "direct-kateryna-andrii",
        "type": "direct",
        "participants": ["kateryna.bondar@example.com", "andrii.melnyk@example.com"],
        "messages": [
            (
                "kateryna.bondar@example.com",
                "Hi Andrii, quick question about the module 2 exercise.",
                9,
            ),
            ("andrii.melnyk@example.com", "Go ahead.", 9),
            (
                "kateryna.bondar@example.com",
                "My query count assertion fails at 4 instead of 2. I used select_related on "
                "the author but the publisher still hits the database.",
                9,
            ),
            (
                "andrii.melnyk@example.com",
                "That is the right instinct. select_related takes a path, so you want "
                "select_related('author', 'publisher') rather than two separate calls.",
                8,
            ),
            ("kateryna.bondar@example.com", "That fixed it. Down to 2 queries. Thank you!", 8),
            (
                "andrii.melnyk@example.com",
                "Good. Keep that assertion in the test, it will catch the next regression.",
                8,
            ),
        ],
    },
    {
        "key": "direct-lukas-sofia",
        "type": "direct",
        "participants": ["lukas.berger@example.com", "sofia.lindqvist@example.com"],
        "messages": [
            (
                "lukas.berger@example.com",
                "Sofia, is the dependency array lesson the right place to ask about "
                "useEffect running twice in development?",
                6,
            ),
            (
                "sofia.lindqvist@example.com",
                "Perfect place. That is strict mode deliberately double-invoking to surface "
                "effects that are not cleanup-safe. It does not happen in production.",
                6,
            ),
            (
                "lukas.berger@example.com",
                "So if double-invoking breaks my effect, the effect is the problem?",
                6,
            ),
            ("sofia.lindqvist@example.com", "Exactly. Add the cleanup and it stops mattering.", 5),
        ],
    },
    {
        "key": "group-django-cohort",
        "type": "group",
        "title": "Django Spring Cohort",
        "participants": [
            "andrii.melnyk@example.com",
            "kateryna.bondar@example.com",
            "tomasz.wisniewski@example.com",
            "aisha.rahman@example.com",
            "noah.callahan@example.com",
        ],
        "owner": "andrii.melnyk@example.com",
        "messages": [
            (
                "andrii.melnyk@example.com",
                "Welcome everyone. Sessions are Monday and Wednesday at 18:00, recordings go "
                "up the same evening.",
                14,
            ),
            ("tomasz.wisniewski@example.com", "Is the recording link the same every week?", 14),
            ("andrii.melnyk@example.com", "Same link, it updates in place.", 14),
            (
                "aisha.rahman@example.com",
                "Anyone else getting a migration conflict after pulling today?",
                11,
            ),
            (
                "kateryna.bondar@example.com",
                "Yes, two 0007 files. makemigrations --merge sorted it for me.",
                11,
            ),
            (
                "andrii.melnyk@example.com",
                "That is the right fix. I will mention it on Wednesday.",
                11,
            ),
            (
                "noah.callahan@example.com",
                "Get 90% off any backend course at cheapcourses.example.com with code SAVE90! "
                "Limited time only!!",
                7,
            ),
            ("tomasz.wisniewski@example.com", "Please stop posting that here.", 7),
            (
                "andrii.melnyk@example.com",
                "Removed the earlier ones. Next one and I hand it to moderation.",
                7,
            ),
        ],
    },
    {
        "key": "group-react-selfpaced",
        "type": "group",
        "title": "React from Scratch: discussion",
        "participants": [
            "sofia.lindqvist@example.com",
            "tomasz.wisniewski@example.com",
            "lukas.berger@example.com",
            "viktor.sokolov@example.com",
            "julia.novak@example.com",
        ],
        "owner": "sofia.lindqvist@example.com",
        "messages": [
            (
                "sofia.lindqvist@example.com",
                "Module 3 is live. The data fetching section replaces the old one entirely.",
                12,
            ),
            (
                "julia.novak@example.com",
                "Does the old exercise still apply or should we redo it?",
                12,
            ),
            ("sofia.lindqvist@example.com", "Redo it, the API shape changed.", 12),
            (
                "viktor.sokolov@example.com",
                "Some people here clearly cannot read documentation. It is not that hard.",
                10,
            ),
            ("lukas.berger@example.com", "That is not necessary.", 10),
            (
                "viktor.sokolov@example.com",
                "If you need this explained twice you should not be in a paid cohort at all. "
                "Embarrassing.",
                10,
            ),
            ("tomasz.wisniewski@example.com", "Reporting this.", 10),
        ],
    },
]

CHAT_MODERATION = {
    # (chat key, index into that chat's message list) -> report
    "reports": [
        {
            "chat": "group-django-cohort",
            "message_index": 6,
            "reporter": "tomasz.wisniewski@example.com",
            "reason": "spam",
            "details": "Affiliate link spam, third time this week.",
            "days_ago": 7,
        },
        {
            "chat": "group-react-selfpaced",
            "message_index": 3,
            "reporter": "lukas.berger@example.com",
            "reason": "harassment",
            "details": "Talking down to the whole group.",
            "days_ago": 10,
        },
        {
            "chat": "group-react-selfpaced",
            "message_index": 5,
            "reporter": "tomasz.wisniewski@example.com",
            "reason": "harassment",
            "details": "Direct personal attack on another student.",
            "days_ago": 10,
        },
        {
            "chat": "group-react-selfpaced",
            "message_index": 5,
            "reporter": "julia.novak@example.com",
            "reason": "harassment",
            "details": "This is the second time today.",
            "days_ago": 10,
        },
    ],
    "actions": [
        {
            "target": "noah.callahan@example.com",
            "moderator": "marcus.feldman@example.com",
            "action": "warning",
            "report": {"chat": "group-django-cohort", "message_index": 6},
            "note": "First formal warning for advertising in a cohort chat.",
            "days_ago": 7,
        },
        {
            "target": "viktor.sokolov@example.com",
            "moderator": "marcus.feldman@example.com",
            "action": "warning",
            "report": {"chat": "group-react-selfpaced", "message_index": 3},
            "note": "Warned about tone towards other students.",
            "days_ago": 10,
        },
        {
            "target": "viktor.sokolov@example.com",
            "moderator": "marcus.feldman@example.com",
            "action": "restrict",
            "note": "Chat access removed after a second, more direct attack.",
            "days_ago": 9,
        },
        {
            "target": "ibrahim.toure@example.com",
            "moderator": "priya.raman@example.com",
            "action": "restrict",
            "note": "Restricted while the hate speech report is investigated.",
            "days_ago": 7,
        },
        {
            "target": "ibrahim.toure@example.com",
            "moderator": "marcus.feldman@example.com",
            "action": "restore",
            "note": "Restored: the quoted text was not his own.",
            "days_ago": 5,
        },
        {
            "target": "julia.novak@example.com",
            "moderator": "priya.raman@example.com",
            "action": "warning",
            "report": {"chat": "group-react-selfpaced", "message_index": 5},
            "note": "Reminder about sharing session recordings outside the cohort.",
            "days_ago": 9,
        },
        {
            "target": "julia.novak@example.com",
            "moderator": "priya.raman@example.com",
            "action": "retract_warning",
            "report": {"chat": "group-react-selfpaced", "message_index": 5},
            "note": "Retracted, wrong account. The recording was shared by someone else.",
            "days_ago": 3,
        },
    ],
    # Active restrictions left in place at the end of the seed.
    "active_restrictions": ["viktor.sokolov@example.com"],
    "blocks": [
        {"blocker": "lukas.berger@example.com", "blocked": "viktor.sokolov@example.com"},
        {"blocker": "tomasz.wisniewski@example.com", "blocked": "viktor.sokolov@example.com"},
    ],
}

HOMEWORK_SPECS = [
    {
        "course": "backend-engineering-django",
        "module_index": 0,
        "title": "Model the bookstore domain",
        "description": (
            "Write the models for authors, books, customers, and orders. Include the "
            "through model for authorship and justify every on_delete choice in a comment."
        ),
        "status": "published",
        "max_score": 100,
        "published_days_ago": 30,
        "due_days_ago": 16,
        "recipients": [
            "kateryna.bondar@example.com",
            "tomasz.wisniewski@example.com",
            "aisha.rahman@example.com",
        ],
        "submissions": [
            {
                "student": "kateryna.bondar@example.com",
                "content": (
                    "Models pushed to the branch. I used PROTECT on the publisher because "
                    "losing a publisher should not silently delete its catalog."
                ),
                "status": "reviewed",
                "score": 92,
                "feedback": (
                    "Strong work. The through model is right and your on_delete reasoning is "
                    "exactly what I was looking for. Add an index on the order status column."
                ),
                "submitted_days_ago": 18,
                "reviewed_days_ago": 16,
            },
            {
                "student": "tomasz.wisniewski@example.com",
                "content": "Submitted. I was not sure about the many-to-many so I used a plain one.",
                "status": "reviewed",
                "score": 74,
                "feedback": (
                    "Works, but you will need the through model in module 3 when we add "
                    "credit order. Worth changing now while it is cheap."
                ),
                "submitted_days_ago": 17,
                "reviewed_days_ago": 15,
            },
            {
                "student": "aisha.rahman@example.com",
                "content": "Done, though I ran out of time on the order model.",
                "status": "submitted",
                "submitted_days_ago": 4,
            },
        ],
    },
    {
        "course": "backend-engineering-django",
        "module_index": 1,
        "title": "Find and fix the N+1",
        "description": (
            "The provided list endpoint fires one query per row. Fix it and add a test that "
            "asserts the query count, so the regression cannot come back."
        ),
        "status": "published",
        "max_score": 50,
        "published_days_ago": 14,
        "due_days_ago": -3,
        "recipients": ["kateryna.bondar@example.com", "tomasz.wisniewski@example.com"],
        "submissions": [
            {
                "student": "kateryna.bondar@example.com",
                "content": "Down from 41 queries to 2. Test asserts on 2.",
                "status": "reviewed",
                "score": 50,
                "feedback": "Perfect, including the assertion. Nothing to add.",
                "submitted_days_ago": 6,
                "reviewed_days_ago": 5,
            },
            {
                "student": "tomasz.wisniewski@example.com",
                "content": "Got it to 3 queries. Not sure where the last one comes from.",
                "status": "submitted",
                "submitted_days_ago": 2,
            },
        ],
    },
    {
        "course": "react-from-scratch",
        "module_index": 1,
        "title": "Lift the filter state",
        "description": (
            "The search box and the results list currently keep separate copies of the "
            "query. Lift it to their common parent and remove the duplicate state."
        ),
        "status": "published",
        "max_score": 40,
        "published_days_ago": 20,
        "due_days_ago": 6,
        "recipients": ["tomasz.wisniewski@example.com", "lukas.berger@example.com"],
        "submissions": [
            {
                "student": "tomasz.wisniewski@example.com",
                "content": "Lifted to the page component. Both children are now controlled.",
                "status": "reviewed",
                "score": 38,
                "feedback": "Clean. Consider a custom hook once a third consumer appears.",
                "submitted_days_ago": 9,
                "reviewed_days_ago": 8,
            },
        ],
    },
    {
        "course": "data-analysis-bootcamp",
        "module_index": 0,
        "title": "Profile the orders export",
        "description": (
            "Establish the grain, count nulls per column, and list every column that should "
            "be unique but is not. One page of findings, no charts yet."
        ),
        "status": "published",
        "max_score": 30,
        "published_days_ago": 11,
        "due_days_ago": -5,
        "recipients": ["aisha.rahman@example.com", "lukas.berger@example.com"],
        "submissions": [
            {
                "student": "lukas.berger@example.com",
                "content": (
                    "Grain is one order line, not one order. Customer email is duplicated "
                    "across 1,204 rows with different casing."
                ),
                "status": "reviewed",
                "score": 30,
                "feedback": "You found the grain trap and the casing issue. Full marks.",
                "submitted_days_ago": 3,
                "reviewed_days_ago": 2,
            },
        ],
    },
    {
        "course": "ux-design-fundamentals",
        "module_index": 0,
        "title": "Run two interviews",
        "description": (
            "Interview two people about the last time they booked a medical appointment. "
            "Send the notes, not a summary."
        ),
        "status": "closed",
        "max_score": 20,
        "published_days_ago": 24,
        "closed_days_ago": 5,
        "due_days_ago": 7,
        "recipients": ["mariya.ivanenko@example.com"],
        "submissions": [
            {
                "student": "mariya.ivanenko@example.com",
                "content": "Both interviews attached as raw notes. The second one went off script.",
                "status": "reviewed",
                "score": 18,
                "feedback": (
                    "Off script is fine, that is where the useful material was. Watch the "
                    "leading question at minute six."
                ),
                "submitted_days_ago": 12,
                "reviewed_days_ago": 10,
            },
        ],
    },
    {
        "course": "fullstack-javascript",
        "module_index": 1,
        "title": "Token refresh end to end",
        "description": (
            "Implement the refresh flow so an expired access token is renewed without "
            "bouncing the user to the login screen. Draft, not yet published."
        ),
        "status": "draft",
        "max_score": 60,
        "recipients": [],
        "submissions": [],
    },
]
