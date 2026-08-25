"""Course catalog content: descriptions, curricula, readings, and quizzes.

Shape of one entry, keyed by course slug:

    "course-slug": {
        "title", "subtitle", "short_description",
        "intro": [<paragraph>, ...],      # opening of full_description
        "audience": <paragraph>,          # "Who this course is for"
        "bullets": [...],                 # "What you will learn"
        "requirements": [...],
        "modules": [
            {
                "title", "description",
                "lessons": [
                    {
                        "title",
                        "video": bool,
                        "reading": {"heading", "paragraphs": [...], "takeaways": [...]},
                        "document": "<file name>",   # optional
                        "preview": bool,             # optional, free preview lesson
                        "test": bool,                # optional, hosts the module test
                    },
                ],
                "test": {... question set ...},      # optional
            },
        ],
    }

Every question set covers all four question types, so the attempt and grading
flow keeps full coverage. `correct_indices` points into `options`; short answers
grade against `sample_answer` plus `accepted_answers`.
"""

COURSE_CONTENT = {
    "backend-engineering-django": {
        "certificate": (
            "Designed and shipped a production REST API with Django and DRF: modelled the domain, "
            "secured it with authentication and permissions, found and fixed the queries that made it "
            "slow, and deployed it from a container pipeline."
        ),
        "title": "Backend Engineering with Django",
        "subtitle": "From an empty folder to a deployed REST API",
        "short_description": (
            "Build a production-grade REST API with Django and DRF: real models, real "
            "permissions, real deploys."
        ),
        "intro": [
            "Most backend tutorials stop at the point where the interesting problems start. "
            "You get a working endpoint, and then nothing about what happens when two users "
            "write the same row, when a query starts scanning a million records, or when the "
            "deploy has to happen on a Friday afternoon.",
            "This course builds one service the whole way through: a bookstore API with "
            "accounts, catalog, orders, and an admin panel. Every module adds a piece you "
            "would actually ship, and we refactor as the requirements grow instead of "
            "pretending we got the design right on the first try.",
        ],
        "audience": (
            "Developers who can write Python and want to own a backend service end to end. "
            "You do not need prior Django experience, but you should be comfortable with "
            "functions, classes, and the command line."
        ),
        "bullets": [
            "Model a real domain with the Django ORM",
            "Design REST endpoints that survive contact with a frontend",
            "Add authentication, permissions, and meaningful tests",
            "Find and fix the queries that make an API slow",
            "Deploy with Docker and a CI pipeline",
        ],
        "requirements": [
            "Comfortable writing Python functions and classes",
            "Basic command line usage (cd, ls, running a script)",
            "A computer with Python 3.11 or newer installed",
        ],
        "modules": [
            {
                "title": "A Django project you can grow into",
                "description": (
                    "Set up the project the way a team would: split settings, environment "
                    "variables, and a layout that still makes sense at fifty models."
                ),
                "lessons": [
                    {
                        "title": "How a request becomes a response",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "The path through Django",
                            "paragraphs": [
                                "A request arrives at the WSGI or ASGI entry point, passes "
                                "through the middleware stack in order, and is matched against "
                                "the URL configuration. The matched view receives a request "
                                "object and must return a response object. Middleware then runs "
                                "again on the way out, in reverse order.",
                                "Almost every confusing Django bug becomes obvious once you can "
                                "say which of those steps you are in. Authentication failures "
                                "live in middleware. A 404 that should have been a 200 lives in "
                                "URL matching. A response that is missing a header was probably "
                                "built before the middleware that adds it.",
                            ],
                            "takeaways": [
                                "Middleware runs in order on the way in and reverse on the way out",
                                "A view takes a request and returns a response, nothing more",
                                "Locate a bug by naming the step it happens in",
                            ],
                        },
                    },
                    {
                        "title": "Settings, environments, and secrets",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Configuration that does not leak",
                            "paragraphs": [
                                "Hard-coded credentials are the single most common way a student "
                                "project ends up on a public repository with a live database "
                                "password in it. Read configuration from the environment, keep a "
                                "committed .env.example that lists the variable names, and keep "
                                "the real .env out of version control.",
                                "Split settings by environment rather than branching on a DEBUG "
                                "flag scattered through the file. Local development, CI, and "
                                "production differ in more than one setting, and a single import "
                                "of a shared base keeps those differences visible in one place.",
                            ],
                            "takeaways": [
                                "Never commit a real secret, commit the variable name instead",
                                "Keep environment differences in one file, not scattered ifs",
                                "A missing required variable should fail loudly at startup",
                            ],
                        },
                    },
                    {
                        "title": "Your first model and migration",
                        "reading": {
                            "heading": "Migrations are code review for your schema",
                            "paragraphs": [
                                "A migration is a Python file describing a schema change. Because "
                                "it is committed alongside the model, a reviewer can see exactly "
                                "what will happen to the database before it happens, and every "
                                "environment applies the same change in the same order.",
                                "Two rules save most of the pain. Generate migrations, never "
                                "hand-write them unless you have a reason. And never edit a "
                                "migration that has already run somewhere else: add a new one "
                                "instead, because the applied history is what other environments "
                                "have recorded.",
                            ],
                            "takeaways": [
                                "Migrations are reviewable artifacts, treat them like code",
                                "Do not edit a migration that has already been applied elsewhere",
                                "Run makemigrations --check in CI to catch model drift",
                            ],
                        },
                        "document": "Django project setup checklist.pdf",
                    },
                    {
                        "title": "Workshop: scaffolding the bookstore API",
                        "video": True,
                        "reading": {
                            "heading": "What we are building",
                            "paragraphs": [
                                "The bookstore has authors, books, customers, and orders. That is "
                                "small enough to hold in your head and large enough to hit every "
                                "problem worth teaching: a many-to-many relation, a status field "
                                "with rules about which transitions are legal, and a query that "
                                "gets slow if you write it the obvious way.",
                                "Work through the scaffolding with the video rather than after "
                                "it. The starter files contain the empty app and the test suite "
                                "we will fill in; if a test fails at the end of this workshop, "
                                "that is expected and we fix it in the next module.",
                            ],
                            "takeaways": [
                                "Four models are enough to demonstrate every core concept",
                                "Start from a failing test suite, not from a blank file",
                                "Commit after each working step so you can roll back cheaply",
                            ],
                        },
                        "document": "Bookstore starter files.zip",
                    },
                ],
                "test": {
                    "title": "Project foundations",
                    "description": "Check that the request cycle and project setup landed.",
                    "passing_score": 60,
                    "duration_minutes": 10,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "In which order does Django process middleware on the way out?",
                            "options": [
                                "The same order as on the way in",
                                "Reverse of the order on the way in",
                                "Alphabetically by class name",
                                "Middleware only runs on the way in",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which of these belong in environment variables rather than in settings.py?",
                            "options": [
                                "SECRET_KEY",
                                "INSTALLED_APPS",
                                "Database password",
                                "The list of middleware",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "It is safe to edit a migration that has already been applied on another environment.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "Which management command creates new migration files from model changes?",
                            "sample_answer": "makemigrations",
                            "accepted_answers": [
                                "python manage.py makemigrations",
                                "manage.py makemigrations",
                            ],
                        },
                    ],
                },
            },
            {
                "title": "Modelling data with the ORM",
                "description": (
                    "Relations, constraints, and the query patterns that decide whether your "
                    "API answers in 20 milliseconds or 2 seconds."
                ),
                "lessons": [
                    {
                        "title": "Relationships: foreign keys and many-to-many",
                        "video": True,
                        "reading": {
                            "heading": "Choosing the right relation",
                            "paragraphs": [
                                "A foreign key says each book has exactly one publisher. A "
                                "many-to-many says a book can have several authors and an author "
                                "several books. The moment you need to store something about the "
                                "relationship itself, such as the order an author is credited in, "
                                "the many-to-many needs an explicit through model.",
                                "Deletion behaviour is part of the design, not an afterthought. "
                                "CASCADE removes children with the parent, PROTECT refuses the "
                                "delete, and SET_NULL keeps the row but forgets the link. Pick "
                                "the one that matches what the business actually wants to happen.",
                            ],
                            "takeaways": [
                                "Data about a relationship belongs on a through model",
                                "on_delete is a business decision, not a default to accept",
                                "Name reverse accessors deliberately with related_name",
                            ],
                        },
                    },
                    {
                        "title": "Querysets and the N+1 problem",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Why the list endpoint got slow",
                            "paragraphs": [
                                "Querysets are lazy: nothing hits the database until you iterate, "
                                "slice, or call something like count(). That laziness is what lets "
                                "you build a query in pieces, and it is also why a loop that "
                                "touches a related object per row quietly fires one query per row.",
                                "select_related follows foreign keys with a join and is right for "
                                "single-valued relations. prefetch_related runs a second query and "
                                "stitches results together in Python, which is what you want for "
                                "many-to-many and reverse relations. Measuring beats guessing: "
                                "count the queries in a test and assert on the number.",
                            ],
                            "takeaways": [
                                "select_related joins, prefetch_related runs a second query",
                                "One query per row in a loop is the classic N+1",
                                "Assert on query counts so a regression fails the build",
                            ],
                        },
                    },
                    {
                        "title": "Constraints, indexes, and integrity",
                        "reading": {
                            "heading": "Let the database enforce the rules",
                            "paragraphs": [
                                "Validation in a serializer protects you from well-behaved "
                                "clients. A database constraint protects you from everything "
                                "else: a management command, a migration, a second service, or a "
                                "race between two simultaneous requests. If a rule genuinely must "
                                "always hold, it belongs in a constraint.",
                                "Indexes are the other half. An index makes reads faster and "
                                "writes slightly slower, so add them for the queries you actually "
                                "run rather than for every column. The query plan tells you "
                                "whether one is being used, and it is worth learning to read.",
                            ],
                            "takeaways": [
                                "Serializer validation is not a substitute for a constraint",
                                "Index for the queries you run, not for every column",
                                "Read the query plan before adding an index on a hunch",
                            ],
                        },
                        "document": "ORM query cookbook.pdf",
                    },
                ],
                "test": {
                    "title": "Data modelling",
                    "description": "Relations, query behaviour, and integrity rules.",
                    "passing_score": 70,
                    "duration_minutes": 15,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Which method is the right fit for loading a many-to-many relation?",
                            "options": [
                                "select_related",
                                "prefetch_related",
                                "only",
                                "defer",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which situations call for an explicit through model?",
                            "options": [
                                "Storing the date a student enrolled",
                                "Linking a book to its single publisher",
                                "Recording the order authors are credited in",
                                "Counting how many tags a post has",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "A queryset sends a query to the database as soon as it is assigned to a variable.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "What is the common name for firing one extra query per row of a result set?",
                            "sample_answer": "N+1 problem",
                            "accepted_answers": ["n+1", "n + 1 query problem", "n plus one"],
                        },
                    ],
                },
            },
            {
                "title": "The API layer and shipping it",
                "description": (
                    "Serializers, viewsets, permissions, tests, and the deploy pipeline that "
                    "puts all of it in front of real users."
                ),
                "lessons": [
                    {
                        "title": "Serializers and validation",
                        "video": True,
                        "reading": {
                            "heading": "Where validation belongs",
                            "paragraphs": [
                                "A serializer has two jobs: turn model instances into JSON, and "
                                "turn untrusted JSON into validated data. Keep the second job "
                                "strict. Field-level validation checks one value, object-level "
                                "validation checks how several values relate, and anything that "
                                "needs a database lookup usually belongs in a service.",
                                "Resist the temptation to put business rules in the serializer. "
                                "A rule such as refusing a second review from the same student is "
                                "not about the shape of the payload, and it will need to hold when "
                                "the row is created from an admin command too.",
                            ],
                            "takeaways": [
                                "Serializers validate shape, services enforce business rules",
                                "Object-level validation is for rules that span fields",
                                "Never trust a client-supplied id without checking ownership",
                            ],
                        },
                    },
                    {
                        "title": "Viewsets, routers, and permissions",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Thin views, explicit permissions",
                            "paragraphs": [
                                "A viewset groups the standard actions for one resource and a "
                                "router turns them into URLs. The value is consistency: every "
                                "resource ends up with the same URL shape, so a frontend "
                                "developer can guess the endpoint correctly the first time.",
                                "Permissions deserve more care than they usually get. Decide the "
                                "default centrally, make public endpoints opt in explicitly, and "
                                "keep object-level checks separate from role checks. An endpoint "
                                "that is public by accident is the kind of bug you find in a "
                                "security review rather than in a test.",
                            ],
                            "takeaways": [
                                "Routers give every resource a predictable URL shape",
                                "Default to authenticated, opt in to public",
                                "Role checks and object ownership checks are different concerns",
                            ],
                        },
                    },
                    {
                        "title": "Testing, Docker, and the deploy",
                        "reading": {
                            "heading": "Shipping without ceremony",
                            "paragraphs": [
                                "Write tests at the level you care about. For an API that means "
                                "hitting the endpoint with a client and asserting on the status "
                                "code and payload, because that is the contract a frontend "
                                "depends on. Unit tests below that level are useful, but they are "
                                "not what tells you the feature works.",
                                "The container image should build without secrets, and migrations "
                                "should run as a separate deploy step rather than at container "
                                "start. Otherwise two containers starting at once will both try "
                                "to migrate, and you will spend an afternoon reading lock traces.",
                            ],
                            "takeaways": [
                                "Test at the endpoint level, that is where the contract lives",
                                "Build images without secrets baked in",
                                "Run migrations as a deploy step, not on container start",
                            ],
                        },
                        "document": "Deployment runbook.pdf",
                    },
                ],
                "test": {
                    "title": "Final assessment",
                    "description": "The capstone quiz across the whole course.",
                    "passing_score": 80,
                    "duration_minutes": 30,
                    "allow_retakes": False,
                    "max_attempts": 1,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Where does a rule like 'a student may leave only one review per course' belong?",
                            "options": [
                                "In the serializer's field validation",
                                "In the service layer, backed by a database constraint",
                                "In the frontend form",
                                "In a middleware",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which are good reasons to run migrations as a separate deploy step?",
                            "options": [
                                "Two containers starting at once would both migrate",
                                "It makes the image smaller",
                                "The build then needs no database credentials",
                                "It removes the need for tests",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "REST APIs are expected to be stateless between requests.",
                            "correct_bool": True,
                        },
                        {
                            "type": "short_answer",
                            "text": "Which HTTP status code should an endpoint return when the caller is authenticated but not allowed?",
                            "sample_answer": "403",
                            "accepted_answers": ["403 forbidden", "forbidden"],
                        },
                    ],
                },
            },
        ],
    },
    "react-from-scratch": {
        "certificate": (
            "Built a complete React application from empty folder to production build: component "
            "boundaries, hooks and state, server data with its loading and error states, forms with "
            "real validation, and a measured approach to rendering performance."
        ),
        "title": "React from Scratch",
        "subtitle": "Components, hooks, and state you can reason about",
        "short_description": (
            "Learn modern React properly: component boundaries, hooks, data fetching, and "
            "state that does not fight you."
        ),
        "intro": [
            "React is small. The confusing part is not the API, it is knowing where a piece "
            "of state should live and when a component is doing too much. Those two "
            "questions decide whether a codebase stays pleasant at ten thousand lines.",
            "We build a single application across the course, a job board with search, "
            "filters, saved listings, and an authenticated area. Each module introduces the "
            "naive version first and then refactors it, because seeing why a pattern exists "
            "beats being told to use it.",
        ],
        "audience": (
            "Developers who know JavaScript and some HTML and CSS, and who have either never "
            "used React or have used it without ever feeling in control of it."
        ),
        "bullets": [
            "Split an interface into components with clear boundaries",
            "Use hooks without the dependency-array guesswork",
            "Fetch, cache, and revalidate server data",
            "Handle forms, validation, and errors properly",
            "Ship a single-page app that behaves well on a slow connection",
        ],
        "requirements": [
            "Comfortable with modern JavaScript (arrow functions, destructuring, modules)",
            "Basic HTML and CSS",
            "Node.js 20 or newer installed",
        ],
        "modules": [
            {
                "title": "Thinking in components",
                "description": (
                    "Rendering, props, and the discipline of drawing boundaries in the right "
                    "places."
                ),
                "lessons": [
                    {
                        "title": "What React actually does",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "Declarative rendering in one page",
                            "paragraphs": [
                                "You describe what the interface should look like for a given "
                                "state, and React works out the minimal set of DOM changes to get "
                                "there. You never write the update steps yourself. That single "
                                "shift is the whole idea, and everything else follows from it.",
                                "The practical consequence is that bugs move. You stop debugging "
                                "'why is this element still on screen' and start debugging 'why "
                                "does the state still say it should be'. That is a much easier "
                                "question to answer, provided your state is somewhere sensible.",
                            ],
                            "takeaways": [
                                "Describe the target UI, not the steps to reach it",
                                "Rendering is a function of state and props",
                                "Most UI bugs are state bugs wearing a costume",
                            ],
                        },
                    },
                    {
                        "title": "Props, composition, and where to cut",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Drawing component boundaries",
                            "paragraphs": [
                                "A good boundary is one where the props list is short and "
                                "obvious. If a component takes eleven props and half of them are "
                                "booleans that switch off parts of the render, that is two "
                                "components pretending to be one.",
                                "Composition is the escape hatch. Passing children, or passing a "
                                "rendered element as a prop, lets a container stay ignorant of "
                                "what it is wrapping. It is almost always better than adding "
                                "another flag to a component that already has too many.",
                            ],
                            "takeaways": [
                                "A long boolean prop list means the component should be split",
                                "Prefer composition over configuration flags",
                                "Name components after what they are, not where they sit",
                            ],
                        },
                    },
                    {
                        "title": "Lists, keys, and conditional rendering",
                        "reading": {
                            "heading": "Why keys matter more than they look",
                            "paragraphs": [
                                "A key tells React which item in a list is which between "
                                "renders. Using the array index looks fine until items get "
                                "reordered, inserted, or removed, at which point React reuses the "
                                "wrong element and you get a form that keeps the previous row's "
                                "typed text.",
                                "Use a stable identifier from the data. If the data genuinely has "
                                "no identifier, that is usually a sign the backend should be "
                                "sending one, not a sign to reach for the index.",
                            ],
                            "takeaways": [
                                "Keys must be stable across renders, not positional",
                                "Index keys break on reorder, insert, and delete",
                                "Missing ids in the payload are a backend conversation",
                            ],
                        },
                        "document": "Component checklist.pdf",
                    },
                    {
                        "title": "Workshop: the job board shell",
                        "video": True,
                        "reading": {
                            "heading": "Building the skeleton",
                            "paragraphs": [
                                "We put the layout, routing, and a static list of hard-coded "
                                "listings in place before touching data fetching. Working against "
                                "fixed data first means that when something breaks in the next "
                                "module, you know it is the network layer and not the render.",
                                "The starter files include the design tokens and a small "
                                "component library so we are not spending the course writing CSS. "
                                "Everything visual is already decided; the work is structural.",
                            ],
                            "takeaways": [
                                "Build against static data before adding the network",
                                "A stable shell makes later bugs easy to localize",
                                "Do not let styling eat the time budget for architecture",
                            ],
                        },
                        "document": "Job board starter files.zip",
                    },
                ],
                "test": {
                    "title": "Components and rendering",
                    "description": "The mental model before we add state.",
                    "passing_score": 60,
                    "duration_minutes": 10,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "What should you use as the key for a list of items?",
                            "options": [
                                "The array index",
                                "A stable identifier from the data",
                                "A random value generated on each render",
                                "The item's position in the sorted order",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which are signs a component should be split?",
                            "options": [
                                "It takes many boolean props that switch off sections",
                                "It renders a list",
                                "Two unrelated features are edited in the same file constantly",
                                "It uses a hook",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "In React you write the DOM update steps yourself.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "What prop lets a component render arbitrary nested content passed by its parent?",
                            "sample_answer": "children",
                            "accepted_answers": ["props.children", "the children prop"],
                        },
                    ],
                },
            },
            {
                "title": "State and hooks",
                "description": (
                    "useState, useEffect, and the rules that stop effects from running at the "
                    "wrong time."
                ),
                "lessons": [
                    {
                        "title": "Local state and lifting it up",
                        "video": True,
                        "reading": {
                            "heading": "Where should this state live?",
                            "paragraphs": [
                                "Start with the state as local as possible. When two components "
                                "need the same value, move it to their nearest common parent and "
                                "pass it down. That is the whole algorithm, and it handles far "
                                "more cases than people expect before reaching for a store.",
                                "Global state is for things that are genuinely global: the "
                                "current user, the theme, a toast queue. Putting form state in a "
                                "global store because it was convenient once is how applications "
                                "become impossible to reason about.",
                            ],
                            "takeaways": [
                                "Keep state as local as it can be",
                                "Lift to the nearest common parent when it must be shared",
                                "Global state is for genuinely global concerns",
                            ],
                        },
                    },
                    {
                        "title": "Effects and dependencies",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Effects are for synchronizing with the outside",
                            "paragraphs": [
                                "An effect exists to synchronize your component with something "
                                "outside React: a subscription, a timer, the document title. If "
                                "you are using one to compute a value from other values, you "
                                "almost certainly want a plain calculation during render instead.",
                                "The dependency array is not a suggestion. Every value from the "
                                "component used inside the effect belongs in it. When that feels "
                                "wrong, the honest fix is usually to move the value out of the "
                                "component or wrap the function it comes from, not to delete the "
                                "entry and hope.",
                            ],
                            "takeaways": [
                                "Effects synchronize with the outside world",
                                "Derived values belong in render, not in an effect",
                                "Fighting the dependency array is a design smell",
                            ],
                        },
                    },
                    {
                        "title": "Forms, validation, and errors",
                        "reading": {
                            "heading": "Controlled inputs without the pain",
                            "paragraphs": [
                                "A controlled input keeps its value in state, which makes "
                                "validation, formatting, and conditional disabling easy. The cost "
                                "is a render on every keystroke, which only matters on genuinely "
                                "large forms and is worth measuring before optimizing.",
                                "Validate on blur and on submit rather than on every keystroke. "
                                "Telling someone their email is invalid while they are still on "
                                "the third character is technically accurate and practically "
                                "hostile.",
                            ],
                            "takeaways": [
                                "Controlled inputs keep validation simple",
                                "Validate on blur and submit, not per keystroke",
                                "Always show the server's error, never swallow it",
                            ],
                        },
                        "document": "Hooks reference sheet.pdf",
                    },
                ],
                "test": {
                    "title": "State and effects",
                    "description": "The part everyone gets wrong at least once.",
                    "passing_score": 70,
                    "duration_minutes": 15,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Two sibling components need the same value. What is the first thing to try?",
                            "options": [
                                "Add a global store",
                                "Lift the state to their nearest common parent",
                                "Duplicate the state in both",
                                "Store it in localStorage",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which belong inside an effect?",
                            "options": [
                                "Subscribing to a websocket",
                                "Computing a filtered list from props",
                                "Setting the document title",
                                "Formatting a date for display",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "Omitting a used value from the dependency array is a safe way to stop an effect re-running.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "What is the name for an input whose value is held in React state?",
                            "sample_answer": "controlled component",
                            "accepted_answers": ["controlled input", "controlled"],
                        },
                    ],
                },
            },
            {
                "title": "Data, performance, and shipping",
                "description": (
                    "Fetching and caching server data, keeping renders cheap, and getting the "
                    "app in front of users."
                ),
                "lessons": [
                    {
                        "title": "Fetching, caching, and loading states",
                        "video": True,
                        "reading": {
                            "heading": "Server data is not component state",
                            "paragraphs": [
                                "Data from an API has properties local state does not: it can be "
                                "stale, it can be shared by several screens, and it may need "
                                "refetching after a mutation. Treating it as ordinary state is "
                                "why so many applications end up with a tangle of manual "
                                "refetch calls.",
                                "Every request has four outcomes and your UI needs all four: "
                                "loading, empty, error, and success. The empty state is the one "
                                "everyone forgets, and it is the one a reviewer will find within "
                                "thirty seconds of opening the app.",
                            ],
                            "takeaways": [
                                "Server data is cache, not component state",
                                "Design loading, empty, error, and success every time",
                                "Refetch after mutations rather than patching by hand",
                            ],
                        },
                    },
                    {
                        "title": "Rendering performance without guesswork",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Measure, then memoize",
                            "paragraphs": [
                                "Most React performance work is premature. Wrapping everything in "
                                "memo adds comparison cost and code noise, and often makes things "
                                "slower. Open the profiler, find the component that actually "
                                "re-renders too often, and fix that one.",
                                "When you do need it, the usual cause is a new object or function "
                                "created on every render being passed as a prop. Stabilizing that "
                                "reference fixes more cases than memoizing the child does.",
                            ],
                            "takeaways": [
                                "Profile before memoizing anything",
                                "Unstable prop references are the usual culprit",
                                "Fewer, larger state updates beat many small ones",
                            ],
                        },
                    },
                    {
                        "title": "Building and deploying the app",
                        "reading": {
                            "heading": "The last mile",
                            "paragraphs": [
                                "A production build strips development warnings, minifies, and "
                                "splits code. Check the bundle size before you ship: a single "
                                "accidentally imported library can double it, and on a slow "
                                "connection that is the difference between usable and abandoned.",
                                "Environment configuration for a frontend is public by "
                                "definition. Anything shipped to the browser can be read by "
                                "anyone using the app, so API keys that must stay secret belong "
                                "behind your own backend.",
                            ],
                            "takeaways": [
                                "Check bundle size as part of the release routine",
                                "Nothing in a frontend build is secret",
                                "Split code so the first screen loads fast",
                            ],
                        },
                        "document": "Release checklist.pdf",
                    },
                ],
                "test": {
                    "title": "Final assessment",
                    "description": "Everything from components through deployment.",
                    "passing_score": 80,
                    "duration_minutes": 25,
                    "allow_retakes": False,
                    "max_attempts": 1,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Which UI state is most often forgotten when rendering a fetched list?",
                            "options": ["Loading", "Empty", "Error", "Success"],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which are reasonable first steps when a screen re-renders too much?",
                            "options": [
                                "Open the profiler and find the component",
                                "Wrap every component in memo",
                                "Stabilize object and function props",
                                "Move all state to a global store",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "An API key placed in a frontend environment variable stays secret from users.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "What is the technique of splitting a bundle so the first screen loads faster called?",
                            "sample_answer": "code splitting",
                            "accepted_answers": ["code-splitting", "lazy loading"],
                        },
                    ],
                },
            },
        ],
    },
    "ux-design-fundamentals": {
        "title": "UX Design Fundamentals",
        "subtitle": "Research, wireframes, and interfaces people can actually use",
        "short_description": (
            "Run honest user research, turn findings into wireframes, and test designs "
            "before anyone writes code."
        ),
        "intro": [
            "Good design is mostly good questions. Before anything gets drawn, someone has "
            "to find out what people are actually trying to do, which is harder than it "
            "sounds because users are polite and will happily agree with whatever you "
            "suggest.",
            "This course runs the full loop twice on a real brief: a booking flow for a "
            "small clinic. You will interview people, synthesize what they said, sketch, "
            "prototype, test with five participants, and then do it again with what you "
            "learned. The second pass is where the course actually happens.",
        ],
        "audience": (
            "Career changers and developers who want to understand design decisions rather "
            "than just execute them. No drawing skill required, and no prior design tooling "
            "experience is assumed."
        ),
        "bullets": [
            "Plan and run interviews without leading the participant",
            "Turn messy notes into findings you can act on",
            "Sketch and wireframe at the right level of fidelity",
            "Build a clickable prototype and test it with five people",
            "Present design decisions with evidence behind them",
        ],
        "requirements": [
            "A free Figma account",
            "Access to five people willing to spend 30 minutes each",
            "No prior design experience",
        ],
        "modules": [
            {
                "title": "Research that tells you something",
                "description": (
                    "Interviews, observation, and the difference between what people say and "
                    "what they do."
                ),
                "lessons": [
                    {
                        "title": "Asking questions that do not lead",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "The interview is a skill, not a form",
                            "paragraphs": [
                                "'Would you use a feature that reminds you about appointments?' "
                                "gets a yes from almost everyone and tells you nothing. 'Walk me "
                                "through the last time you missed an appointment' gets you a "
                                "story, and stories contain the details you could not have "
                                "thought to ask about.",
                                "Ask about the past, not the future. People are poor predictors "
                                "of their own behaviour and excellent reporters of what they "
                                "actually did last Tuesday. When they start speculating, steer "
                                "them gently back to a specific occasion.",
                            ],
                            "takeaways": [
                                "Ask about specific past events, never about hypotheticals",
                                "Silence is a tool, let the participant fill it",
                                "If they agree with everything, your questions are leading",
                            ],
                        },
                    },
                    {
                        "title": "Synthesis: from notes to findings",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Making sense of six hours of transcript",
                            "paragraphs": [
                                "Write one observation per note, in the participant's own words "
                                "where possible. Then group the notes by what they have in "
                                "common and name each group afterwards. Naming the groups first "
                                "guarantees you will find what you already believed.",
                                "A finding is not a quote and not a feature request. It is a "
                                "statement about behaviour that several participants support, "
                                "phrased so that a design decision can follow from it. If you "
                                "cannot imagine two different designs answering it, it is too "
                                "specific.",
                            ],
                            "takeaways": [
                                "One observation per note, in their words",
                                "Group first, name the groups afterwards",
                                "A finding describes behaviour, not a feature",
                            ],
                        },
                        "document": "Interview guide template.pdf",
                    },
                    {
                        "title": "Personas, journeys, and when to skip them",
                        "reading": {
                            "heading": "Artifacts that earn their keep",
                            "paragraphs": [
                                "A journey map is useful when the problem spans several steps and "
                                "several days, because it makes the gaps between steps visible. A "
                                "persona is useful when a team keeps designing for itself. Both "
                                "are useless when produced as a deliverable nobody reads.",
                                "Make the artifact only if you can name the decision it will "
                                "inform. Otherwise you have spent a week producing a poster.",
                            ],
                            "takeaways": [
                                "Journey maps show the gaps between steps",
                                "Personas fight the habit of designing for yourself",
                                "If it informs no decision, do not make it",
                            ],
                        },
                    },
                ],
                "test": {
                    "title": "Research fundamentals",
                    "description": "Interview technique and synthesis.",
                    "passing_score": 60,
                    "duration_minutes": 10,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Which question is least likely to lead the participant?",
                            "options": [
                                "Would you use a reminder feature?",
                                "Walk me through the last appointment you missed.",
                                "Don't you find the current booking form confusing?",
                                "How much would you pay for this?",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which are good synthesis practices?",
                            "options": [
                                "One observation per note",
                                "Naming your groups before sorting",
                                "Grouping notes before naming the groups",
                                "Keeping only the quotes that support your idea",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "People are reliable predictors of their own future behaviour.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "How many participants are usually enough to surface most usability problems in one round?",
                            "sample_answer": "5",
                            "accepted_answers": ["five", "5 participants", "about five"],
                        },
                    ],
                },
            },
            {
                "title": "From sketch to tested prototype",
                "description": (
                    "Wireframes at the right fidelity, a clickable prototype, and a usability "
                    "test that produces decisions."
                ),
                "lessons": [
                    {
                        "title": "Sketching and fidelity",
                        "video": True,
                        "reading": {
                            "heading": "Low fidelity buys you honesty",
                            "paragraphs": [
                                "A polished mockup invites feedback about colour. A rough sketch "
                                "invites feedback about whether the flow makes sense. Early on "
                                "you want the second kind, so keep it deliberately unfinished for "
                                "longer than feels comfortable.",
                                "Sketch several options before refining one. The first idea is "
                                "rarely the best and is always the hardest to abandon once it has "
                                "been made to look nice.",
                            ],
                            "takeaways": [
                                "Fidelity signals what kind of feedback you want",
                                "Draw several options before refining any",
                                "Polish late, structure first",
                            ],
                        },
                    },
                    {
                        "title": "Prototyping and running the test",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Five people, one afternoon",
                            "paragraphs": [
                                "Give the participant a task, not a tour. 'Book a follow-up "
                                "appointment for next week' tells you where the flow breaks; "
                                "'what do you think of this screen' tells you about their manners. "
                                "Then stay quiet and watch where they hesitate.",
                                "Hesitation is the signal. People rarely say a design is "
                                "confusing, but they will pause, scroll back, or click the wrong "
                                "thing and correct themselves. Note those moments with a "
                                "timestamp and you will have your fix list by the end of the day.",
                            ],
                            "takeaways": [
                                "Give tasks, never a guided tour",
                                "Watch for hesitation, not for compliments",
                                "Five participants per round, then fix and repeat",
                            ],
                        },
                        "document": "Usability test script.pdf",
                    },
                    {
                        "title": "Presenting decisions with evidence",
                        "reading": {
                            "heading": "Defending a design without arguing about taste",
                            "paragraphs": [
                                "Present the finding, then the decision it led to, then the "
                                "alternative you rejected and why. That order moves the "
                                "conversation from opinion to evidence, and it makes "
                                "disagreement productive because people can argue with the "
                                "finding rather than with you.",
                                "Be honest about what you do not know. A design presented with "
                                "its open questions listed is far more credible than one "
                                "presented as finished, and it invites exactly the help you need.",
                            ],
                            "takeaways": [
                                "Finding, then decision, then rejected alternative",
                                "Name your open questions out loud",
                                "Evidence turns taste arguments into design discussions",
                            ],
                        },
                    },
                ],
                "test": {
                    "title": "Design and testing",
                    "description": "Fidelity, prototyping, and usability testing.",
                    "passing_score": 70,
                    "duration_minutes": 15,
                    "allow_retakes": True,
                    "max_attempts": 2,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Why keep early wireframes deliberately rough?",
                            "options": [
                                "It saves licence costs",
                                "It steers feedback towards structure rather than styling",
                                "Rough work tests better with users",
                                "It is faster to print",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which signals matter most while observing a usability test?",
                            "options": [
                                "Hesitation before a click",
                                "Compliments about the colour scheme",
                                "Scrolling back to re-read something",
                                "How quickly they say they like it",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "You should explain each screen to the participant before they attempt the task.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "What do you give a participant instead of a tour of the interface?",
                            "sample_answer": "a task",
                            "accepted_answers": ["task", "tasks", "a realistic task"],
                        },
                    ],
                },
            },
        ],
    },
    "data-analysis-bootcamp": {
        "certificate": (
            "Took a raw sales export through the full analysis cycle: established its grain, cleaned "
            "and joined it without losing records, answered business questions in SQL and pandas, and "
            "presented the result as a dashboard with its limits stated."
        ),
        "title": "Data Analysis Bootcamp",
        "subtitle": "From spreadsheets to dashboards people trust",
        "short_description": (
            "Clean messy data, query it with SQL, analyse it with pandas, and present it "
            "so decisions actually change."
        ),
        "intro": [
            "Analysis is mostly cleaning. The glamorous part, the model or the chart, is "
            "maybe a fifth of the work; the rest is finding out that the country column "
            "contains 'UK', 'U.K.', 'United Kingdom' and one row that just says 'yes'.",
            "We work with a real export from an online store: sixty thousand orders, "
            "inconsistent formatting, duplicated customers, and a returns table that does "
            "not quite join. By the end you will have a dashboard answering four business "
            "questions and a written note on how much you trust each number.",
        ],
        "audience": (
            "Analysts working in spreadsheets who are hitting the ceiling, and developers "
            "who need to answer data questions without a data team."
        ),
        "bullets": [
            "Profile a new dataset and find what is wrong with it",
            "Write SQL that answers business questions, including joins and window functions",
            "Reshape and aggregate data with pandas",
            "Choose a chart that communicates instead of decorating",
            "Say honestly how confident you are in a number",
        ],
        "requirements": [
            "Comfortable with spreadsheets (formulas, pivot tables)",
            "Some Python basics are helpful but not required",
            "A laptop that can install Python and a database client",
        ],
        "modules": [
            {
                "title": "Getting data into a usable state",
                "description": (
                    "Profiling, cleaning, and the judgement calls that decide what your "
                    "numbers mean."
                ),
                "lessons": [
                    {
                        "title": "Profiling a dataset you have never seen",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "The first hour with new data",
                            "paragraphs": [
                                "Before any analysis, answer four questions: how many rows, what "
                                "is the grain of one row, which columns have missing values, and "
                                "which columns should be unique but are not. Those four turn up "
                                "most serious problems in about twenty minutes.",
                                "The grain matters more than anything else. If you think one row "
                                "is an order and it is actually an order line, every total you "
                                "produce will be wrong in a way that looks plausible, which is "
                                "the worst kind of wrong.",
                            ],
                            "takeaways": [
                                "Establish the grain of a row before anything else",
                                "Count nulls and duplicates before analysing",
                                "Plausible-looking wrong numbers are the dangerous ones",
                            ],
                        },
                    },
                    {
                        "title": "Cleaning without destroying evidence",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Every cleaning step is a decision",
                            "paragraphs": [
                                "Dropping rows with missing values is a decision about who "
                                "disappears from your analysis. Filling them with the mean is a "
                                "decision to pretend they were average. Neither is wrong, but "
                                "both change the answer, and both need to be written down.",
                                "Keep the raw file untouched and do cleaning in a script that can "
                                "be re-run. When someone questions a number three weeks later, "
                                "the script is the answer, and you will not have to remember what "
                                "you clicked.",
                            ],
                            "takeaways": [
                                "Never edit the raw file, script the cleaning",
                                "Write down every assumption you make while cleaning",
                                "Dropping rows silently excludes a group of people",
                            ],
                        },
                        "document": "Data cleaning checklist.pdf",
                    },
                    {
                        "title": "Joining tables that do not quite match",
                        "reading": {
                            "heading": "When the join loses rows",
                            "paragraphs": [
                                "Count rows before and after every join. If the number went up, "
                                "you have duplicates on the join key. If it went down, you used "
                                "an inner join where you needed a left join, and some records "
                                "quietly left the building.",
                                "Mismatched keys are usually formatting, not missing data: "
                                "trailing spaces, different casing, leading zeros stripped by a "
                                "spreadsheet. Normalize both sides before joining rather than "
                                "accepting a 94 percent match rate.",
                            ],
                            "takeaways": [
                                "Row count before and after every join",
                                "More rows means duplicate keys, fewer means an inner join",
                                "Most key mismatches are formatting problems",
                            ],
                        },
                    },
                ],
                "test": {
                    "title": "Data quality",
                    "description": "Profiling, cleaning, and joining.",
                    "passing_score": 60,
                    "duration_minutes": 12,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "The row count went up after a join. What is the most likely cause?",
                            "options": [
                                "An inner join dropped records",
                                "Duplicate values on the join key",
                                "Missing values in a column",
                                "The tables were sorted differently",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which should you establish before starting analysis?",
                            "options": [
                                "What one row represents",
                                "Which chart you will use",
                                "Which columns should be unique",
                                "The colour palette",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "Filling missing values with the column mean is a neutral step with no effect on results.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "What is the term for what a single row in a table represents?",
                            "sample_answer": "grain",
                            "accepted_answers": ["granularity", "the grain", "row grain"],
                        },
                    ],
                },
            },
            {
                "title": "SQL for real questions",
                "description": (
                    "Aggregation, joins, and window functions, driven by questions a manager "
                    "would actually ask."
                ),
                "lessons": [
                    {
                        "title": "Aggregation and grouping",
                        "video": True,
                        "reading": {
                            "heading": "GROUP BY, and why your total is wrong",
                            "paragraphs": [
                                "Aggregation collapses many rows into one. The trap is filtering: "
                                "WHERE runs before grouping and HAVING runs after, so a condition "
                                "in the wrong place changes which rows contribute to the total "
                                "rather than which totals are shown.",
                                "Joining before aggregating multiplies rows. If each order joins "
                                "to three order lines and you then sum the order total, you have "
                                "tripled your revenue. Aggregate first, then join, whenever the "
                                "shape allows it.",
                            ],
                            "takeaways": [
                                "WHERE filters rows, HAVING filters groups",
                                "Joining before aggregating inflates sums",
                                "Sanity check totals against a known number",
                            ],
                        },
                    },
                    {
                        "title": "Window functions in practice",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Ranking, running totals, and period comparisons",
                            "paragraphs": [
                                "A window function calculates across a set of rows related to the "
                                "current one without collapsing them. That is exactly what you "
                                "need for 'each customer's first order', 'running revenue by "
                                "day', or 'this month against the same month last year'.",
                                "The mental model is simple: PARTITION BY decides which rows are "
                                "in the window, ORDER BY decides the sequence inside it. Almost "
                                "every window function question is really a question about those "
                                "two clauses.",
                            ],
                            "takeaways": [
                                "Window functions keep rows, aggregates collapse them",
                                "PARTITION BY sets the window, ORDER BY sets the sequence",
                                "Running totals and rankings are the two everyday uses",
                            ],
                        },
                        "document": "SQL patterns reference.pdf",
                    },
                    {
                        "title": "Reshaping data with pandas",
                        "reading": {
                            "heading": "Long, wide, and back again",
                            "paragraphs": [
                                "Long format has one measurement per row and is what most "
                                "analysis and plotting tools want. Wide format spreads a variable "
                                "across columns and is what people want to read. Knowing how to "
                                "move between the two removes a surprising amount of friction.",
                                "Chained operations are readable when each step does one thing. "
                                "When a chain grows past about five steps, assign an intermediate "
                                "variable with a meaningful name; future you will be grateful.",
                            ],
                            "takeaways": [
                                "Analyse in long format, present in wide",
                                "One operation per step keeps chains readable",
                                "Name intermediate results once a chain gets long",
                            ],
                        },
                    },
                ],
                "test": {
                    "title": "Querying and reshaping",
                    "description": "SQL aggregation, window functions, and pandas.",
                    "passing_score": 70,
                    "duration_minutes": 20,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Which clause filters rows after grouping has happened?",
                            "options": ["WHERE", "HAVING", "ORDER BY", "LIMIT"],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which tasks are a natural fit for window functions?",
                            "options": [
                                "A running total by day",
                                "Counting total rows in a table",
                                "Ranking orders within each customer",
                                "Deleting duplicate rows",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "Joining a one-to-many relation before summing can inflate the total.",
                            "correct_bool": True,
                        },
                        {
                            "type": "short_answer",
                            "text": "Which window clause decides which rows belong to the same window?",
                            "sample_answer": "PARTITION BY",
                            "accepted_answers": ["partition by", "partition"],
                        },
                    ],
                },
            },
            {
                "title": "Communicating the answer",
                "description": (
                    "Charts that inform, dashboards that stay correct, and honest statements "
                    "of confidence."
                ),
                "lessons": [
                    {
                        "title": "Choosing a chart",
                        "video": True,
                        "reading": {
                            "heading": "The chart is an argument",
                            "paragraphs": [
                                "Pick the chart from the comparison you want the reader to make. "
                                "Change over time is a line. Comparison between categories is a "
                                "bar. Part of a whole is usually still a bar, because people read "
                                "angles badly and lengths well.",
                                "Every element that does not carry information is competing with "
                                "the element that does. Remove the gradient, the shadow, and the "
                                "third dimension. Label directly rather than making the reader "
                                "bounce between a legend and the data.",
                            ],
                            "takeaways": [
                                "Choose the chart from the comparison, not from taste",
                                "Direct labels beat legends",
                                "Decoration competes with information",
                            ],
                        },
                    },
                    {
                        "title": "Building the dashboard",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "A dashboard is a product with users",
                            "paragraphs": [
                                "Start from the decisions the dashboard should support and work "
                                "backwards to the numbers. A dashboard showing everything "
                                "available supports no decision at all, and it will be quietly "
                                "abandoned within a month.",
                                "Put the definition next to the number. 'Active customers' means "
                                "something different to every person reading it, and the "
                                "arguments that follow cost more time than writing the definition "
                                "would have.",
                            ],
                            "takeaways": [
                                "Design backwards from the decision",
                                "Define every metric in place",
                                "Fewer numbers, better chosen, get used more",
                            ],
                        },
                        "document": "Dashboard review checklist.pdf",
                    },
                    {
                        "title": "Saying how confident you are",
                        "reading": {
                            "heading": "Caveats are part of the answer",
                            "paragraphs": [
                                "Every number you produce rests on cleaning decisions, a join "
                                "that lost some rows, and a definition someone picked. Stating "
                                "those alongside the number is not hedging, it is the difference "
                                "between analysis and assertion.",
                                "Give the caveat a size. 'This excludes about 3 percent of orders "
                                "with missing region' lets a reader decide whether it matters. "
                                "'There may be some data quality issues' does not.",
                            ],
                            "takeaways": [
                                "State the assumptions behind each headline number",
                                "Quantify the caveat, do not just mention it",
                                "Being explicit about limits builds trust, not doubt",
                            ],
                        },
                    },
                ],
                "test": {
                    "title": "Final assessment",
                    "description": "Cleaning, querying, and communicating.",
                    "passing_score": 75,
                    "duration_minutes": 25,
                    "allow_retakes": False,
                    "max_attempts": 1,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Which chart best shows change in one metric over 24 months?",
                            "options": ["Pie chart", "Line chart", "Scatter plot", "Treemap"],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which belong next to a headline number on a dashboard?",
                            "options": [
                                "The definition of the metric",
                                "The SQL query that produced it",
                                "The size of any known exclusion",
                                "The name of the database server",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "A dashboard is more useful the more metrics it displays.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "Which SQL join type keeps all rows from the left table even without a match?",
                            "sample_answer": "LEFT JOIN",
                            "accepted_answers": ["left join", "left outer join"],
                        },
                    ],
                },
            },
        ],
    },
    "fullstack-javascript": {
        "certificate": (
            "Built and connected both halves of a web application: an Express API over a real "
            "database, a React frontend, and token authentication with refresh and logout working end "
            "to end."
        ),
        "title": "Fullstack JavaScript",
        "subtitle": "An Express API and a React frontend, wired together properly",
        "short_description": (
            "Build both halves of an application: a Node and Express API, a React UI, and "
            "authentication that actually holds."
        ),
        "intro": [
            "Knowing the frontend and the backend separately is not the same as knowing how "
            "they meet. The interesting bugs live in between: a token that expires "
            "mid-session, a CORS preflight nobody expected, an error the API returns and the "
            "UI silently swallows.",
            "We build a recipe-sharing app across the course. The API comes first, then the "
            "UI, then the two are connected and everything that was theoretically fine stops "
            "working. Fixing that is the point.",
        ],
        "audience": (
            "Developers who have touched either React or Node and want to be able to build "
            "and ship a complete application on their own."
        ),
        "bullets": [
            "Build a REST API with Express and a real database",
            "Design a schema and keep it migrated",
            "Connect a React frontend to your own API",
            "Implement token authentication end to end",
            "Handle errors so the user learns something useful",
        ],
        "requirements": [
            "Comfortable with JavaScript and async/await",
            "Some React or willingness to learn it alongside",
            "Node.js 20 or newer",
        ],
        "modules": [
            {
                "title": "The API half",
                "description": "Express, routing, persistence, and error handling.",
                "lessons": [
                    {
                        "title": "Express, routing, and middleware",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "A request pipeline you assemble yourself",
                            "paragraphs": [
                                "Express gives you very little by default, which is both its "
                                "appeal and its risk. Every request passes through the middleware "
                                "you registered, in the order you registered it, and anything you "
                                "forgot to add simply does not happen.",
                                "Order matters more than people expect. Body parsing must come "
                                "before any handler that reads the body, authentication before "
                                "anything that needs a user, and the error handler last, because "
                                "Express identifies it by its four arguments and its position.",
                            ],
                            "takeaways": [
                                "Middleware order is part of the design",
                                "The error handler goes last and takes four arguments",
                                "Nothing happens by default, you assemble it",
                            ],
                        },
                    },
                    {
                        "title": "Persistence and schema",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "The database is not an afterthought",
                            "paragraphs": [
                                "Decide the schema before writing endpoints. Endpoints are cheap "
                                "to change; a table with a hundred thousand rows and a column "
                                "that should have been a foreign key is not.",
                                "Use migrations from the first day even for a project of your "
                                "own. The habit costs ten minutes to establish and saves the "
                                "afternoon where production and local have quietly diverged.",
                            ],
                            "takeaways": [
                                "Schema decisions outlive endpoint decisions",
                                "Migrations from day one, even solo",
                                "Constraints in the database, not only in code",
                            ],
                        },
                        "document": "API schema worksheet.pdf",
                    },
                    {
                        "title": "Errors, status codes, and logging",
                        "reading": {
                            "heading": "Failing in a way somebody can debug",
                            "paragraphs": [
                                "Return the status code that describes what happened: 400 for a "
                                "malformed request, 401 for missing credentials, 403 for "
                                "forbidden, 404 for missing, 409 for conflict. A blanket 500 for "
                                "everything makes the frontend guess, and it will guess wrong.",
                                "Log with enough context to find the request again: a request "
                                "id, the user, and the route. Logging the stack trace alone tells "
                                "you what broke but not for whom or why.",
                            ],
                            "takeaways": [
                                "The status code is part of the API contract",
                                "Include a request id in every log line",
                                "Never return a stack trace to the client",
                            ],
                        },
                    },
                ],
                "test": {
                    "title": "Backend fundamentals",
                    "description": "Express, persistence, and error handling.",
                    "passing_score": 60,
                    "duration_minutes": 12,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Which status code fits a request from an authenticated user who lacks permission?",
                            "options": ["400", "401", "403", "404"],
                            "correct_indices": [2],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which are true of Express middleware?",
                            "options": [
                                "It runs in registration order",
                                "It runs alphabetically",
                                "The error handler takes four arguments",
                                "Body parsing is enabled by default",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "Returning the full stack trace to the client is acceptable in production.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "Which status code signals a conflict, such as a duplicate resource?",
                            "sample_answer": "409",
                            "accepted_answers": ["409 conflict", "conflict"],
                        },
                    ],
                },
            },
            {
                "title": "The frontend half and the seam",
                "description": (
                    "Connecting React to your own API, authentication, and the problems that "
                    "only appear once both halves are running."
                ),
                "lessons": [
                    {
                        "title": "Calling your API from React",
                        "video": True,
                        "reading": {
                            "heading": "The seam between the two halves",
                            "paragraphs": [
                                "Keep every call to the API in one module. When the base URL "
                                "changes, when a header must be added to every request, or when "
                                "you need to retry on a 401, you want one place to edit rather "
                                "than forty call sites.",
                                "CORS surprises almost everyone once. The browser sends a "
                                "preflight request for anything beyond the simplest call, and if "
                                "your API does not answer it, the real request never happens. The "
                                "error in the console is misleading; the fix is on the server.",
                            ],
                            "takeaways": [
                                "One API module, not fetch calls scattered everywhere",
                                "CORS is configured on the server, not the client",
                                "A failed preflight hides the real request entirely",
                            ],
                        },
                    },
                    {
                        "title": "Authentication end to end",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Tokens, refresh, and logout",
                            "paragraphs": [
                                "A short-lived access token plus a longer-lived refresh token is "
                                "the standard shape. The access token authorizes requests; the "
                                "refresh token exists only to get a new access token, which "
                                "limits the damage if one leaks.",
                                "Logout is more than deleting the token from the browser. The "
                                "refresh token must be invalidated on the server, otherwise "
                                "anyone who copied it can keep minting access tokens long after "
                                "the user believed they had signed out.",
                            ],
                            "takeaways": [
                                "Short access token, longer refresh token",
                                "Logout must invalidate the refresh token server-side",
                                "Refresh transparently, do not bounce the user to login",
                            ],
                        },
                        "document": "Auth flow diagram.pdf",
                    },
                    {
                        "title": "Running both halves in production",
                        "reading": {
                            "heading": "Two processes, one product",
                            "paragraphs": [
                                "Frontend and backend deploy independently, which means for a "
                                "few minutes they will be at different versions. Design the API "
                                "so an older frontend keeps working: add fields rather than "
                                "renaming them, and remove things only after nothing calls them.",
                                "Configuration differs on both sides. The frontend needs the API "
                                "URL at build time, and the backend needs to allow the frontend's "
                                "origin. Getting either wrong produces a blank page and a console "
                                "error, so check both before blaming the code.",
                            ],
                            "takeaways": [
                                "Assume the two halves are briefly at different versions",
                                "Add fields, do not rename them",
                                "Blank page plus console error usually means configuration",
                            ],
                        },
                    },
                ],
                "test": {
                    "title": "Final assessment",
                    "description": "The full stack, including the seam between halves.",
                    "passing_score": 75,
                    "duration_minutes": 20,
                    "allow_retakes": False,
                    "max_attempts": 1,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Where is CORS configured?",
                            "options": [
                                "In the browser",
                                "On the server that receives the request",
                                "In the React build config",
                                "In the DNS records",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which are required for a logout that actually ends the session?",
                            "options": [
                                "Removing the token from the browser",
                                "Clearing the browser cache",
                                "Invalidating the refresh token on the server",
                                "Changing the API base URL",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "Renaming an API response field is safe to deploy at any time.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "What request does a browser send before certain cross-origin calls?",
                            "sample_answer": "preflight",
                            "accepted_answers": ["preflight request", "options request", "options"],
                        },
                    ],
                },
            },
        ],
    },
    "advanced-kubernetes": {
        "title": "Advanced Kubernetes",
        "subtitle": "Operators, autoscaling, and observability",
        "short_description": (
            "Operate Kubernetes past the tutorial stage: custom operators, sensible "
            "autoscaling, and observability that answers questions at 3am."
        ),
        "intro": [
            "Getting a pod running is a weekend. Keeping a cluster healthy while a team "
            "deploys twenty times a day is a different discipline, and it is mostly about "
            "the things that are invisible until they fail.",
            "This course assumes you already have workloads in a cluster and want to stop "
            "being surprised by them. We cover the control loop properly, write an operator, "
            "and build the dashboards you will actually look at during an incident.",
        ],
        "audience": (
            "Engineers already running workloads on Kubernetes who want to move from "
            "following instructions to making decisions."
        ),
        "bullets": [
            "Reason about the control loop and reconciliation",
            "Write a custom controller for your own resource",
            "Autoscale on signals that mean something",
            "Instrument workloads so incidents are debuggable",
            "Harden a cluster without making it unusable",
        ],
        "requirements": [
            "Comfortable with kubectl and YAML manifests",
            "Have deployed at least one application to a cluster",
            "Some Go is helpful for the operator module",
        ],
        "modules": [
            {
                "title": "The control loop, properly understood",
                "description": (
                    "Reconciliation, desired versus actual state, and why your resource is "
                    "stuck in Pending."
                ),
                "lessons": [
                    {
                        "title": "Desired state and reconciliation",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "Everything is a loop",
                            "paragraphs": [
                                "Kubernetes does not execute your commands. You record a desired "
                                "state, and controllers keep comparing that against the actual "
                                "state and taking one step to close the gap. Every strange "
                                "behaviour makes sense once you ask which controller is looping "
                                "and what it currently believes.",
                                "This is also why deleting things does not always work the way "
                                "you expect. If a controller still holds the desired state, it "
                                "will helpfully recreate what you just removed, and you will "
                                "delete the same pod four times before checking its owner.",
                            ],
                            "takeaways": [
                                "You declare desired state, controllers close the gap",
                                "Ask which controller owns a resource before deleting it",
                                "Every step is one iteration, not a transaction",
                            ],
                        },
                    },
                    {
                        "title": "Scheduling, requests, and limits",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Why the pod will not schedule",
                            "paragraphs": [
                                "Requests decide where a pod can be placed; limits decide when it "
                                "gets throttled or killed. Setting requests too high wastes half "
                                "the cluster, setting them too low means the scheduler packs "
                                "nodes until everything is starved.",
                                "Memory and CPU behave differently under pressure. Exceeding a "
                                "CPU limit throttles the container, which is survivable. "
                                "Exceeding a memory limit terminates it, which is not, and that "
                                "asymmetry should shape how you set the two.",
                            ],
                            "takeaways": [
                                "Requests drive scheduling, limits drive enforcement",
                                "CPU over-limit throttles, memory over-limit kills",
                                "Base requests on measurements, not on round numbers",
                            ],
                        },
                        "document": "Resource sizing worksheet.pdf",
                    },
                ],
                "test": {
                    "title": "Cluster fundamentals",
                    "description": "Control loop and scheduling behaviour.",
                    "passing_score": 70,
                    "duration_minutes": 15,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "What happens when a container exceeds its memory limit?",
                            "options": [
                                "It is throttled",
                                "It is terminated",
                                "It is migrated to another node",
                                "Nothing, limits are advisory",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which statements about requests and limits are correct?",
                            "options": [
                                "Requests influence which node a pod lands on",
                                "Limits influence which node a pod lands on",
                                "Exceeding a CPU limit throttles the container",
                                "Requests are enforced at runtime",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "Deleting a pod owned by a controller permanently removes it.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "What is the name of the loop controllers run to close the gap between desired and actual state?",
                            "sample_answer": "reconciliation",
                            "accepted_answers": [
                                "reconcile loop",
                                "control loop",
                                "reconciliation loop",
                            ],
                        },
                    ],
                },
            },
            {
                "title": "Operators and observability",
                "description": (
                    "Extending the API with your own resource, and instrumenting workloads so "
                    "incidents are survivable."
                ),
                "lessons": [
                    {
                        "title": "Writing a custom controller",
                        "video": True,
                        "reading": {
                            "heading": "Your own resource, your own loop",
                            "paragraphs": [
                                "A custom resource definition adds a new kind to the API. On its "
                                "own it stores data and does nothing; the controller you write is "
                                "what gives it behaviour, following exactly the same reconcile "
                                "pattern as the built-in controllers.",
                                "Make reconcile idempotent and assume it will be called far more "
                                "often than you expect, sometimes for objects that have not "
                                "changed. A reconcile function with side effects that are unsafe "
                                "to repeat will fail in ways that are extremely hard to "
                                "reproduce.",
                            ],
                            "takeaways": [
                                "A CRD without a controller is just storage",
                                "Reconcile must be idempotent",
                                "Expect reconcile to run more often than necessary",
                            ],
                        },
                    },
                    {
                        "title": "Metrics, logs, and useful alerts",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Instrument for the questions you will ask",
                            "paragraphs": [
                                "During an incident you ask three things: is it broken, for whom, "
                                "and since when. Instrument to answer those. A hundred metrics "
                                "nobody has ever queried are worse than five that are on the "
                                "dashboard everyone opens first.",
                                "Alert on symptoms rather than causes. 'Error rate above two "
                                "percent for five minutes' is worth waking someone for. 'CPU "
                                "above 80 percent' is not, because it is frequently fine, and an "
                                "alert people learn to ignore is worse than no alert.",
                            ],
                            "takeaways": [
                                "Instrument for incident questions, not for completeness",
                                "Alert on symptoms users feel, not on resource numbers",
                                "An ignored alert is worse than a missing one",
                            ],
                        },
                        "document": "Observability starter kit.zip",
                    },
                ],
            },
        ],
    },
    "marketing-essentials": {
        "title": "Marketing Essentials",
        "subtitle": "Channels, funnels, and the metrics that matter",
        "short_description": (
            "Understand how customers find you, where they drop off, and which numbers are "
            "worth acting on."
        ),
        "intro": [
            "Marketing looks like a collection of tactics until you see the funnel behind "
            "it. Once you can name the stage a problem lives in, the choice of tactic "
            "mostly makes itself.",
            "This course keeps to fundamentals that outlast platform changes: how demand is "
            "created and captured, how to read a funnel, and how to run a small campaign "
            "with a budget you can defend afterwards.",
        ],
        "audience": (
            "Founders, freelancers, and anyone who has been handed responsibility for "
            "marketing without a background in it."
        ),
        "bullets": [
            "Map the funnel from first touch to repeat purchase",
            "Choose channels based on where your customers already are",
            "Write copy that describes value rather than features",
            "Measure a campaign honestly, including what failed",
        ],
        "requirements": [
            "No prior marketing experience",
            "A product, service, or project you can use as the example",
        ],
        "modules": [
            {
                "title": "The funnel",
                "description": "Awareness, consideration, conversion, retention, and where they leak.",
                "lessons": [
                    {
                        "title": "How people actually find things",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "Created demand and captured demand",
                            "paragraphs": [
                                "Someone searching for 'accounting software for freelancers' has "
                                "already decided they need something; you are competing to be "
                                "chosen. Someone reading an article about late invoices has not "
                                "decided anything yet. Those are two different jobs and they need "
                                "different messages.",
                                "Most wasted budget comes from mixing them up: running a "
                                "conversion-focused advertisement at people who have never heard "
                                "of the problem, or writing gentle educational content for "
                                "someone with a credit card already in hand.",
                            ],
                            "takeaways": [
                                "Captured demand competes on choice, created demand on awareness",
                                "Match the message to the stage, not to the channel",
                                "Most wasted spend is a stage mismatch",
                            ],
                        },
                    },
                    {
                        "title": "Reading a funnel and finding the leak",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Fix the biggest drop first",
                            "paragraphs": [
                                "Write the conversion rate at each step and look for the largest "
                                "fall. Doubling traffic to a page that converts at half a percent "
                                "is far more expensive than fixing the page, and the fix is "
                                "usually clarity rather than persuasion.",
                                "Beware of averages across segments. A blended conversion rate "
                                "can hide one channel performing well and another performing "
                                "terribly, and the average tells you to do slightly less of both.",
                            ],
                            "takeaways": [
                                "Find the largest drop, fix that first",
                                "Traffic is the expensive fix, clarity is the cheap one",
                                "Segment before trusting a conversion rate",
                            ],
                        },
                        "document": "Funnel worksheet.pdf",
                    },
                ],
                "test": {
                    "title": "Funnel basics",
                    "description": "Demand types and funnel reading.",
                    "passing_score": 60,
                    "duration_minutes": 10,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "A landing page converts at 0.5 percent. What is usually the cheapest first move?",
                            "options": [
                                "Double the advertising budget",
                                "Improve the clarity of the page",
                                "Add another channel",
                                "Lower the price",
                            ],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which describe captured demand?",
                            "options": [
                                "Someone searching for a specific product category",
                                "Someone reading a general interest article",
                                "Someone comparing two named vendors",
                                "Someone who has never encountered the problem",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "A blended conversion rate across channels is a reliable basis for decisions.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "What is the term for the stage of the funnel where an existing customer buys again?",
                            "sample_answer": "retention",
                            "accepted_answers": ["repeat purchase", "retention stage"],
                        },
                    ],
                },
            },
            {
                "title": "Channels and measurement",
                "description": "Choosing where to spend attention, and reporting honestly on it.",
                "lessons": [
                    {
                        "title": "Picking channels you can sustain",
                        "video": True,
                        "reading": {
                            "heading": "Two channels done well",
                            "paragraphs": [
                                "Every channel has a cost in attention as well as money. Running "
                                "six channels badly produces less than running two well, and it "
                                "makes measurement almost impossible because nothing accumulates "
                                "enough data to be readable.",
                                "Choose based on where your customers already spend time and on "
                                "what you can personally sustain for six months. A channel you "
                                "abandon after three weeks has cost you the setup and returned "
                                "nothing.",
                            ],
                            "takeaways": [
                                "Two channels done well beat six done badly",
                                "Sustainability matters as much as reach",
                                "Thin data across many channels cannot be read",
                            ],
                        },
                    },
                    {
                        "title": "Reporting a campaign honestly",
                        "reading": {
                            "heading": "What to say when it did not work",
                            "paragraphs": [
                                "Report the result, the spend, and what you would do differently. "
                                "A campaign that failed and is clearly explained is worth more to "
                                "the next decision than a vague success, because it eliminates an "
                                "option.",
                                "Attribution is genuinely hard, and pretending otherwise damages "
                                "your credibility. Say which numbers you trust and why, and note "
                                "where the same customer may be counted in two places.",
                            ],
                            "takeaways": [
                                "A clearly explained failure has real value",
                                "State which numbers you trust and which you do not",
                                "Attribution is approximate, say so",
                            ],
                        },
                        "document": "Campaign report template.pdf",
                    },
                ],
            },
        ],
    },
    "photography-basics": {
        "title": "Photography Basics",
        "subtitle": "Light, composition, and editing that does not overdo it",
        "short_description": (
            "Take control of your camera, learn to see light, and edit photographs without "
            "ruining them."
        ),
        "intro": [
            "A better camera makes a smaller difference than most beginners expect. "
            "Understanding light, and being patient enough to wait for it, makes a very "
            "large one.",
            "We work through the exposure triangle, composition, and a restrained editing "
            "workflow. Every module ends with an assignment shot on whatever camera you "
            "have, including a phone.",
        ],
        "audience": (
            "Complete beginners, and people who have owned a camera for years while leaving "
            "it in automatic mode."
        ),
        "bullets": [
            "Control exposure with aperture, shutter, and ISO",
            "Recognize and use available light",
            "Compose photographs that hold attention",
            "Edit with restraint in a repeatable workflow",
        ],
        "requirements": [
            "Any camera, including a phone camera",
            "Free editing software (we use Darktable)",
        ],
        "modules": [
            {
                "title": "Exposure and light",
                "description": "The three controls, and learning to read the light you are given.",
                "lessons": [
                    {
                        "title": "The exposure triangle",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "Three controls, one result",
                            "paragraphs": [
                                "Aperture, shutter speed, and ISO all change brightness, and each "
                                "changes something else as well: depth of field, motion blur, and "
                                "noise respectively. That second effect is the reason you choose "
                                "one over another, since any of the three can make the picture "
                                "brighter.",
                                "Decide what the photograph needs first. A portrait with a soft "
                                "background starts from aperture. A moving subject starts from "
                                "shutter speed. ISO is what you adjust last, to make the other "
                                "two work in the light you actually have.",
                            ],
                            "takeaways": [
                                "Each control has a side effect, that is why you choose",
                                "Start from the effect you want, not from brightness",
                                "ISO is the compromise you make last",
                            ],
                        },
                    },
                    {
                        "title": "Seeing light",
                        "video": True,
                        "test": True,
                        "reading": {
                            "heading": "Direction, quality, colour",
                            "paragraphs": [
                                "Light has a direction, a hardness, and a colour, and those three "
                                "describe most of what makes a photograph work. Hard light from "
                                "the side reveals texture. Soft light from the front flatters "
                                "faces. Neither is better; they are different tools.",
                                "The cheapest improvement available to any beginner is timing. "
                                "The same scene an hour after sunrise and at midday is two "
                                "different photographs, and no amount of editing will convert one "
                                "into the other.",
                            ],
                            "takeaways": [
                                "Describe light by direction, hardness, and colour",
                                "Side light reveals texture, front light flattens it",
                                "Timing beats equipment, consistently",
                            ],
                        },
                        "document": "Exposure practice sheet.pdf",
                    },
                ],
                "test": {
                    "title": "Exposure and light",
                    "description": "The three controls and reading available light.",
                    "passing_score": 60,
                    "duration_minutes": 10,
                    "allow_retakes": True,
                    "max_attempts": 3,
                    "questions": [
                        {
                            "type": "single_choice",
                            "text": "Which control most directly affects depth of field?",
                            "options": ["Shutter speed", "Aperture", "ISO", "White balance"],
                            "correct_indices": [1],
                        },
                        {
                            "type": "multiple_choice",
                            "text": "Which are side effects of the exposure controls?",
                            "options": [
                                "Motion blur from shutter speed",
                                "Colour shift from aperture",
                                "Noise from high ISO",
                                "Depth of field from ISO",
                            ],
                            "correct_indices": [0, 2],
                        },
                        {
                            "type": "true_false",
                            "text": "Hard side light is generally better than soft front light.",
                            "correct_bool": False,
                        },
                        {
                            "type": "short_answer",
                            "text": "What is the collective name for aperture, shutter speed, and ISO?",
                            "sample_answer": "exposure triangle",
                            "accepted_answers": ["the exposure triangle", "exposure"],
                        },
                    ],
                },
            },
            {
                "title": "Composition and editing",
                "description": "Arranging a frame, and a restrained editing workflow.",
                "lessons": [
                    {
                        "title": "Composing a frame",
                        "video": True,
                        "reading": {
                            "heading": "Decide what to leave out",
                            "paragraphs": [
                                "Composition is subtraction. Most weak photographs contain three "
                                "interesting things competing with each other, and the fix is to "
                                "move closer, change angle, or wait until two of them leave.",
                                "Rules such as thirds are starting points, not requirements. They "
                                "are useful precisely because breaking them deliberately produces "
                                "an effect, which is impossible if you were never aware of them.",
                            ],
                            "takeaways": [
                                "Composition is mostly deciding what to exclude",
                                "Move your feet before changing lens",
                                "Know the rules so that breaking them is a choice",
                            ],
                        },
                    },
                    {
                        "title": "A restrained editing workflow",
                        "reading": {
                            "heading": "The order that keeps things natural",
                            "paragraphs": [
                                "Work in a fixed order: exposure and white balance first, then "
                                "contrast, then local adjustments, then sharpening last. Editing "
                                "out of order means re-doing earlier steps, and it is how people "
                                "end up at three in the morning with an orange photograph.",
                                "Step away and look again before exporting. Adjustments creep "
                                "upward while you stare at them, and the version that looked "
                                "balanced after twenty minutes usually does not the next day.",
                            ],
                            "takeaways": [
                                "Fixed order: exposure, contrast, local, sharpen",
                                "Adjustments creep upward the longer you look",
                                "Review the next day before publishing",
                            ],
                        },
                        "document": "Editing workflow.pdf",
                    },
                ],
            },
        ],
    },
    "sql-for-analysts": {
        "title": "SQL for Analysts",
        "subtitle": "Query the database yourself",
        "short_description": (
            "Stop waiting on the data team: write your own queries, from a first SELECT to "
            "multi-table reports."
        ),
        "intro": [
            "Most analytical questions are two joins and a GROUP BY away from an answer. "
            "The gap between having the question and having the answer is usually access "
            "and confidence rather than difficulty.",
            "This is a short, practical course on a copy of a real sales database. Every "
            "lesson ends with a question a colleague might genuinely ask, and the exercise "
            "is to answer it.",
        ],
        "audience": "Analysts, product managers, and anyone who currently requests data from someone else.",
        "bullets": [
            "Write SELECT queries with filtering and sorting",
            "Join tables without losing or duplicating rows",
            "Aggregate to answer business questions",
            "Recognize when a result looks wrong",
        ],
        "requirements": ["Comfortable with spreadsheets", "Access to any SQL client"],
        "modules": [
            {
                "title": "Querying one table",
                "description": "SELECT, WHERE, ORDER BY, and reading a result set critically.",
                "lessons": [
                    {
                        "title": "Your first SELECT",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "Asking the database a question",
                            "paragraphs": [
                                "A query names the columns you want, the table they live in, and "
                                "the conditions rows must meet. That is genuinely most of it, and "
                                "everything more advanced is a variation on those three parts.",
                                "Get into the habit of limiting your results while exploring. A "
                                "query returning two million rows to a client is slow for you and "
                                "rude to everyone else using the database.",
                            ],
                            "takeaways": [
                                "Columns, table, condition: that is the shape",
                                "Limit results while exploring",
                                "Read the first ten rows before trusting a count",
                            ],
                        },
                    },
                    {
                        "title": "Filtering, NULL, and the traps",
                        "reading": {
                            "heading": "NULL is not a value",
                            "paragraphs": [
                                "NULL means unknown, so comparing to it with equals never matches, "
                                "not even against another NULL. Use IS NULL and IS NOT NULL, and "
                                "remember that a NOT IN list containing a NULL will quietly return "
                                "nothing at all.",
                                "This is the single most common source of a query that runs "
                                "without error and returns the wrong answer. When a result is "
                                "empty and you expected rows, check for NULLs first.",
                            ],
                            "takeaways": [
                                "NULL means unknown, comparisons with it are never true",
                                "Use IS NULL, never equals",
                                "An unexpectedly empty result often means a NULL",
                            ],
                        },
                        "document": "SQL cheat sheet.pdf",
                    },
                ],
            },
            {
                "title": "Combining tables",
                "description": "Joins and aggregation, and checking that the result makes sense.",
                "lessons": [
                    {
                        "title": "Joins without losing rows",
                        "video": True,
                        "reading": {
                            "heading": "Inner, left, and what happens to the count",
                            "paragraphs": [
                                "An inner join keeps only rows matching on both sides. A left "
                                "join keeps everything from the left table and fills the rest "
                                "with NULL. Choosing the wrong one silently removes records, "
                                "which is why counting before and after is a habit worth having.",
                                "If your row count went up, the join key is not unique on one "
                                "side. That is not always a bug, but it is always something you "
                                "should have decided deliberately rather than discovered later.",
                            ],
                            "takeaways": [
                                "Inner drops non-matches, left keeps them",
                                "Count rows before and after every join",
                                "A rising count means a non-unique key",
                            ],
                        },
                    },
                    {
                        "title": "Aggregating for a report",
                        "reading": {
                            "heading": "GROUP BY and sanity checks",
                            "paragraphs": [
                                "Grouping collapses rows into one per group, and every column you "
                                "select must either be grouped or aggregated. The error message "
                                "when you forget is unfriendly but the rule is simple.",
                                "Always check a total against something you know independently. "
                                "If last month's revenue in your query does not match the figure "
                                "everyone quotes in meetings, find out why before presenting it.",
                            ],
                            "takeaways": [
                                "Every selected column is grouped or aggregated",
                                "Check totals against an independently known number",
                                "Explain a discrepancy before presenting either figure",
                            ],
                        },
                        "document": "Practice questions.pdf",
                    },
                ],
            },
        ],
    },
    "intro-to-devops": {
        "title": "Introduction to DevOps",
        "subtitle": "Pipelines, containers, and the culture around them",
        "short_description": (
            "Understand continuous integration, containers, and the working habits that "
            "make frequent releases safe."
        ),
        "intro": [
            "DevOps is often sold as a toolchain. The tools matter, but the reason they "
            "exist is a working habit: making releases small and frequent enough that any "
            "single one is boring.",
            "We build a pipeline for a small service, from a failing test in CI through a "
            "container image to a deployment that can be rolled back in under a minute.",
        ],
        "audience": "Developers who want to understand what happens after their code is merged.",
        "bullets": [
            "Set up continuous integration that actually blocks bad merges",
            "Build and publish a container image",
            "Deploy with a rollback you have practised",
            "Understand why small releases are safer",
        ],
        "requirements": ["Comfortable with git", "Any programming language background"],
        "modules": [
            {
                "title": "Continuous integration",
                "description": "Tests that block a merge, and pipelines that stay fast enough to trust.",
                "lessons": [
                    {
                        "title": "A pipeline that blocks bad merges",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "CI is only useful if it can say no",
                            "paragraphs": [
                                "A pipeline that reports a failure nobody is required to act on "
                                "is decoration. The value comes from the merge being blocked, "
                                "which means the checks must be trustworthy enough that people "
                                "accept the block instead of overriding it.",
                                "That puts a hard constraint on flakiness and speed. A suite that "
                                "fails randomly one time in ten teaches everyone to re-run it "
                                "rather than read it, and a pipeline that takes forty minutes "
                                "encourages large batched merges, which is the opposite of what "
                                "you wanted.",
                            ],
                            "takeaways": [
                                "The block is the point, not the report",
                                "Flaky tests destroy trust faster than missing ones",
                                "Slow pipelines push teams towards large risky merges",
                            ],
                        },
                    },
                    {
                        "title": "Containers and reproducible builds",
                        "reading": {
                            "heading": "Same image everywhere",
                            "paragraphs": [
                                "The point of an image is that the artifact tested in CI is "
                                "byte-identical to the one running in production. Rebuilding per "
                                "environment throws that away and reintroduces the class of bug "
                                "the whole approach was meant to remove.",
                                "Keep images small and free of secrets. Build-time secrets end up "
                                "in layers and can be extracted from the published image, which "
                                "is a surprise nobody wants to have during a security review.",
                            ],
                            "takeaways": [
                                "Build once, promote the same image between environments",
                                "Secrets belong in the runtime environment, never in a layer",
                                "Smaller images deploy faster and expose less",
                            ],
                        },
                        "document": "Pipeline template.zip",
                    },
                ],
            },
        ],
    },
    "wordpress-site-building": {
        "title": "Building Sites with WordPress",
        "subtitle": "Themes, plugins, and launching a client site",
        "short_description": (
            "Plan, build, and launch a small business website on WordPress without writing "
            "much code."
        ),
        "intro": [
            "WordPress still runs a large share of the web, and for a small business site "
            "it remains a sensible default: cheap hosting, a content editor non-technical "
            "clients can use, and a plugin for almost anything.",
            "This short course covers the practical path from an empty install to a live "
            "site, with the maintenance conversation that most freelancers forget to have "
            "until something breaks.",
        ],
        "audience": "Freelancers and small business owners building their first website.",
        "bullets": [
            "Structure content before choosing a theme",
            "Pick plugins without breaking the site",
            "Launch with backups and updates configured",
        ],
        "requirements": ["No coding experience required", "Access to any hosting account"],
        "modules": [
            {
                "title": "From empty install to launch",
                "description": "Content structure, theme choice, and the pre-launch checklist.",
                "lessons": [
                    {
                        "title": "Structure before styling",
                        "preview": True,
                        "video": True,
                        "reading": {
                            "heading": "Decide the pages first",
                            "paragraphs": [
                                "Write the page list and the navigation before looking at a "
                                "single theme. Choosing a theme first means the site's structure "
                                "gets decided by whatever the demo content happened to include, "
                                "which is rarely what the business needs.",
                                "Ask the client what a visitor should do on each page. If the "
                                "answer is unclear, the page probably should not exist, and "
                                "removing it now is much easier than after it has been styled.",
                            ],
                            "takeaways": [
                                "Page list and navigation come before theme choice",
                                "Every page needs one clear action",
                                "Deleting a page is cheapest before it is designed",
                            ],
                        },
                    },
                    {
                        "title": "Plugins, backups, and handover",
                        "reading": {
                            "heading": "The part that happens after launch",
                            "paragraphs": [
                                "Each plugin is code you did not write running on your client's "
                                "site. Install as few as you can, check when each was last "
                                "updated, and remove anything you tried and abandoned rather than "
                                "leaving it deactivated.",
                                "Agree who is responsible for updates and backups before "
                                "handover, in writing. The uncomfortable conversation about an "
                                "outdated plugin is much easier before the site is defaced than "
                                "afterwards.",
                            ],
                            "takeaways": [
                                "Fewer plugins, each actively maintained",
                                "Delete abandoned plugins, do not just deactivate them",
                                "Agree maintenance responsibility in writing at handover",
                            ],
                        },
                        "document": "Launch checklist.pdf",
                    },
                ],
            },
        ],
    },
}
