# Structured QA demo catalog used by the teacher seed command.

from datetime import date
from decimal import Decimal

REVISION_COMMENT = "Please add more details to the final assessment section and specify the expected learning outcomes."

COURSES = (
    {
        "slug": "demo-qa-software-testing-fundamentals",
        "title": "Software Testing Fundamentals",
        "subtitle": "Build a strong foundation in practical software quality assurance",
        "short_description": "A practical introduction to testing principles, documentation, bug "
        "reporting, SDLC, and STLC.",
        "description": "Learn how professional QA teams prevent defects, document coverage, report "
        "actionable bugs, and select effective test techniques. Guided examples and a "
        "final practice project turn core theory into repeatable workplace skills.",
        "level": "beginner",
        "primary": "self_paced",
        "status": "published",
        "created": date(2025, 11, 18),
        "published": date(2025, 12, 2),
        "duration": 18,
        "passing_score": 75,
        "certificate": True,
        "certificate_description": "Successfully completed practical training in software testing "
        "fundamentals and test design.",
        "sale": True,
        "discount": 15,
        "formats": {
            "self_paced": {
                "price": Decimal("89.00"),
                "installments": (3, Decimal("30.00")),
                "access_days": 365,
            }
        },
        "modules": (
            (
                "Introduction to Software Testing",
                (
                    {
                        "title": "What Is Quality Assurance?",
                        "duration": 24,
                        "quiz": None,
                        "preview": True,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "QA vs QC vs Testing",
                        "duration": 28,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "SDLC and STLC in Practice",
                        "duration": 36,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
            (
                "Test Documentation",
                (
                    {
                        "title": "Writing Effective Test Cases",
                        "duration": 42,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                    {
                        "title": "Building Risk-Based Checklists",
                        "duration": 34,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Bug Reports Developers Can Reproduce",
                        "duration": 40,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
            (
                "Testing Techniques",
                (
                    {
                        "title": "Equivalence Partitioning",
                        "duration": 35,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Boundary Value Analysis",
                        "duration": 38,
                        "quiz": "testing-techniques",
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Positive and Negative Testing",
                        "duration": 31,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                ),
            ),
            (
                "Final Assessment",
                (
                    {
                        "title": "Practice Project: Test a Registration Flow",
                        "duration": 75,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                    {
                        "title": "Software Testing Fundamentals — Final Quiz",
                        "duration": 30,
                        "quiz": "fundamentals-final",
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                ),
            ),
        ),
    },
    {
        "slug": "demo-qa-manual-qa-job-ready",
        "title": "Manual QA: From Zero to Job Ready",
        "subtitle": "Hands-on preparation for your first manual QA role",
        "short_description": "A complete manual QA program covering requirements, web and mobile "
        "testing, bug tracking, and a real project.",
        "description": "Follow the workflow of a junior QA engineer from requirement review through "
        "release testing. Build portfolio-ready test documentation, investigate browser "
        "and mobile defects, and complete a realistic end-to-end QA project.",
        "level": "beginner",
        "primary": "group",
        "status": "published",
        "created": date(2026, 1, 12),
        "published": date(2026, 2, 3),
        "duration": 48,
        "passing_score": 80,
        "certificate": True,
        "certificate_description": "Completed the Manual QA job-ready program and its applied project.",
        "sale": False,
        "discount": None,
        "formats": {
            "group": {
                "price": Decimal("349.00"),
                "installments": (3, Decimal("117.00")),
                "start": date(2026, 9, 8),
                "unlock": "sequential",
            }
        },
        "cohort": {
            "name": "Manual QA — September 2026",
            "size": 12,
            "months": 3,
            "hours": 6,
            "start": date(2026, 9, 8),
            "deadline": date(2026, 9, 1),
            "schedule": ((1, "18:30", "20:00"), (3, "18:30", "20:00")),
        },
        "modules": (
            (
                "QA Foundations",
                (
                    {
                        "title": "The QA Role and Product Quality",
                        "duration": 40,
                        "quiz": None,
                        "preview": True,
                        "unlock_after_days": 0,
                        "resource": False,
                    },
                    {
                        "title": "Exploratory Testing Workshop",
                        "duration": 55,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 3,
                        "resource": False,
                    },
                ),
            ),
            (
                "Requirements Analysis",
                (
                    {
                        "title": "Finding Ambiguity in Requirements",
                        "duration": 40,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 7,
                        "resource": False,
                    },
                    {
                        "title": "Create a Requirements Traceability Checklist",
                        "duration": 55,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 10,
                        "resource": True,
                    },
                ),
            ),
            (
                "Web Application Testing",
                (
                    {
                        "title": "Browser, UI, and Functional Testing",
                        "duration": 40,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 14,
                        "resource": False,
                    },
                    {
                        "title": "Test an E-commerce Checkout",
                        "duration": 55,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 17,
                        "resource": False,
                    },
                ),
            ),
            (
                "Bug Tracking",
                (
                    {
                        "title": "Defect Lifecycle and Severity",
                        "duration": 40,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 21,
                        "resource": False,
                    },
                    {
                        "title": "Build a Professional Bug Report Set",
                        "duration": 55,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 24,
                        "resource": True,
                    },
                ),
            ),
            (
                "Mobile Testing",
                (
                    {
                        "title": "Mobile Platforms and Device Coverage",
                        "duration": 40,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 28,
                        "resource": False,
                    },
                    {
                        "title": "Test a Mobile Onboarding Flow",
                        "duration": 55,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 31,
                        "resource": False,
                    },
                ),
            ),
            (
                "Real QA Project",
                (
                    {
                        "title": "Planning an End-to-End Test Cycle",
                        "duration": 40,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 35,
                        "resource": False,
                    },
                    {
                        "title": "Portfolio Project Review and Retrospective",
                        "duration": 55,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 38,
                        "resource": True,
                    },
                ),
            ),
        ),
    },
    {
        "slug": "demo-qa-api-testing-postman",
        "title": "API Testing with Postman",
        "subtitle": "Confidently test REST APIs and automate repeatable checks",
        "short_description": "Learn HTTP, REST, authentication, JSON validation, API scenarios, and "
        "Postman automation.",
        "description": "Move beyond UI-only testing by inspecting requests and responses directly. Build "
        "Postman collections, validate contracts and business rules, handle "
        "authentication, and automate regression checks with scripts and environments.",
        "level": "intermediate",
        "primary": "scheduled",
        "status": "published",
        "created": date(2026, 3, 9),
        "published": date(2026, 3, 28),
        "duration": 24,
        "passing_score": 78,
        "certificate": True,
        "certificate_description": "Demonstrated practical REST API testing and Postman automation "
        "skills.",
        "sale": True,
        "discount": 20,
        "formats": {
            "scheduled": {
                "price": Decimal("159.00"),
                "installments": None,
                "start": date(2026, 9, 14),
                "unlock": "date_based",
            }
        },
        "modules": (
            (
                "HTTP Fundamentals",
                (
                    {
                        "title": "Requests, Responses, and Headers",
                        "duration": 35,
                        "quiz": None,
                        "preview": True,
                        "unlock_after_days": 0,
                        "resource": False,
                    },
                    {
                        "title": "Inspect HTTP Traffic",
                        "duration": 50,
                        "quiz": "http-fundamentals",
                        "preview": False,
                        "unlock_after_days": 2,
                        "resource": False,
                    },
                ),
            ),
            (
                "REST APIs",
                (
                    {
                        "title": "Resources, Methods, and Status Codes",
                        "duration": 35,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 5,
                        "resource": False,
                    },
                    {
                        "title": "Design REST Test Coverage",
                        "duration": 50,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 7,
                        "resource": False,
                    },
                ),
            ),
            (
                "Postman Basics",
                (
                    {
                        "title": "Workspaces, Requests, and Environments",
                        "duration": 35,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 10,
                        "resource": False,
                    },
                    {
                        "title": "Build Your First Collection",
                        "duration": 50,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 12,
                        "resource": True,
                    },
                ),
            ),
            (
                "Authentication",
                (
                    {
                        "title": "API Keys, Basic Auth, and Bearer Tokens",
                        "duration": 35,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 15,
                        "resource": False,
                    },
                    {
                        "title": "Test Protected Endpoints",
                        "duration": 50,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 17,
                        "resource": False,
                    },
                ),
            ),
            (
                "API Test Scenarios",
                (
                    {
                        "title": "Positive, Negative, and Contract Tests",
                        "duration": 35,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 20,
                        "resource": False,
                    },
                    {
                        "title": "Validate JSON Responses",
                        "duration": 50,
                        "quiz": "api-scenarios",
                        "preview": False,
                        "unlock_after_days": 22,
                        "resource": False,
                    },
                ),
            ),
            (
                "Postman Collections and Automation",
                (
                    {
                        "title": "Variables and Collection Runner",
                        "duration": 35,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 25,
                        "resource": False,
                    },
                    {
                        "title": "Automate a Regression Collection",
                        "duration": 50,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": 27,
                        "resource": True,
                    },
                ),
            ),
        ),
    },
    {
        "slug": "demo-qa-python-selenium-automation",
        "title": "Automation Testing with Python & Selenium",
        "subtitle": "Create maintainable browser automation from the ground up",
        "short_description": "A practical automation course covering Python, Selenium, locators, Page "
        "Objects, Pytest, and a final project.",
        "description": "Write readable Python tests, control browsers with Selenium WebDriver, choose "
        "robust locators, structure Page Objects, and run maintainable suites with "
        "Pytest. Finish with a portfolio automation project.",
        "level": "intermediate",
        "primary": "group",
        "status": "review",
        "created": date(2026, 5, 14),
        "published": None,
        "duration": 42,
        "passing_score": 80,
        "certificate": True,
        "certificate_description": "Completed applied browser automation training with Python, Selenium, "
        "and Pytest.",
        "sale": False,
        "discount": None,
        "formats": {
            "individual": {
                "price": Decimal("499.00"),
                "installments": (4, Decimal("125.00")),
                "max_students": 5,
            },
            "group": {
                "price": Decimal("289.00"),
                "installments": (3, Decimal("97.00")),
                "start": date(2026, 10, 5),
                "unlock": "sequential",
            },
        },
        "cohort": {
            "name": "Python Automation — October 2026",
            "size": 10,
            "months": 4,
            "hours": 6,
            "start": date(2026, 10, 5),
            "deadline": date(2026, 9, 28),
            "schedule": ((0, "18:30", "20:00"), (2, "18:30", "20:00")),
        },
        "slots": ((4, "16:00", "17:00"), (5, "10:00", "11:00"), (5, "12:00", "13:00")),
        "modules": (
            (
                "Python for QA",
                (
                    {
                        "title": "Python Syntax for Testers",
                        "duration": 42,
                        "quiz": None,
                        "preview": True,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Build Data-Driven Test Utilities",
                        "duration": 65,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
            (
                "Selenium Basics",
                (
                    {
                        "title": "WebDriver and Browser Sessions",
                        "duration": 42,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Automate a Login Flow",
                        "duration": 65,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                ),
            ),
            (
                "Locators and Web Elements",
                (
                    {
                        "title": "Reliable CSS and XPath Locators",
                        "duration": 42,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Handle Forms, Waits, and Dynamic UI",
                        "duration": 65,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                ),
            ),
            (
                "Page Object Model",
                (
                    {
                        "title": "Designing Page Objects",
                        "duration": 42,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Refactor a Test Suite",
                        "duration": 65,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                ),
            ),
            (
                "Pytest",
                (
                    {
                        "title": "Fixtures, Parameters, and Assertions",
                        "duration": 42,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Run and Report a Pytest Suite",
                        "duration": 65,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
            (
                "Automation Project",
                (
                    {
                        "title": "Planning Maintainable Coverage",
                        "duration": 42,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Build a Portfolio Automation Framework",
                        "duration": 65,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
        ),
    },
    {
        "slug": "demo-qa-sql-for-qa-engineers",
        "title": "SQL for QA Engineers",
        "subtitle": "Validate backend data with practical SQL queries",
        "short_description": "SQL essentials for retrieving test data, filtering records, joins, "
        "aggregation, subqueries, and backend validation.",
        "description": "Learn the SQL a QA engineer uses every week. Query test data safely, verify "
        "application behavior against database state, combine tables, summarize results, "
        "and investigate inconsistencies through hands-on exercises.",
        "level": "beginner",
        "primary": "self_paced",
        "status": "draft",
        "created": date(2026, 6, 17),
        "published": None,
        "duration": 20,
        "passing_score": 75,
        "certificate": True,
        "certificate_description": "Completed practical SQL training for software quality assurance.",
        "sale": True,
        "discount": 10,
        "formats": {
            "self_paced": {"price": Decimal("109.00"), "installments": None, "access_days": 270}
        },
        "modules": (
            (
                "Databases for Testers",
                (
                    {
                        "title": "Relational Data and QA Workflows",
                        "duration": 30,
                        "quiz": None,
                        "preview": True,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Explore a Product Database",
                        "duration": 45,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
            (
                "SELECT and Filtering",
                (
                    {
                        "title": "SELECT, WHERE, and Sorting",
                        "duration": 30,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Retrieve Focused Test Data",
                        "duration": 45,
                        "quiz": "sql-filtering",
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
            (
                "JOINs",
                (
                    {
                        "title": "Combining Related Tables",
                        "duration": 30,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Validate Orders Across Tables",
                        "duration": 45,
                        "quiz": "sql-joins",
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
            (
                "Aggregation",
                (
                    {
                        "title": "COUNT, SUM, GROUP BY, and HAVING",
                        "duration": 30,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Check Reporting Metrics",
                        "duration": 45,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
            (
                "Subqueries",
                (
                    {
                        "title": "Nested Queries and EXISTS",
                        "duration": 30,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Investigate Data Inconsistencies",
                        "duration": 45,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
            (
                "QA Database Practice",
                (
                    {
                        "title": "Safe Backend Validation",
                        "duration": 30,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Complete a Database QA Investigation",
                        "duration": 45,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
        ),
    },
    {
        "slug": "demo-qa-interview-preparation",
        "title": "QA Interview Preparation",
        "subtitle": "Turn QA knowledge into confident interview answers",
        "short_description": "Focused Manual QA interview preparation with theory, practical cases, API "
        "and SQL questions, CV guidance, and mock interviews.",
        "description": "Review core theory, solve realistic interview exercises, explain your test "
        "strategy clearly, and prepare concise examples from practical work. Individual "
        "sessions focus on feedback, mock interviews, and a targeted job-search plan.",
        "level": "intermediate",
        "primary": "individual",
        "status": "needs_revision",
        "created": date(2026, 8, 4),
        "published": None,
        "duration": 12,
        "passing_score": 70,
        "certificate": False,
        "certificate_description": "",
        "sale": False,
        "discount": None,
        "formats": {
            "individual": {
                "price": Decimal("239.00"),
                "installments": (2, Decimal("120.00")),
                "max_students": 8,
            }
        },
        "slots": ((1, "15:00", "16:00"), (3, "15:00", "16:00")),
        "modules": (
            (
                "QA Theory Review",
                (
                    {
                        "title": "Core QA Concepts Interviewers Expect",
                        "duration": 35,
                        "quiz": None,
                        "preview": True,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Explain Testing Decisions Clearly",
                        "duration": 50,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                ),
            ),
            (
                "Test Design Questions",
                (
                    {
                        "title": "Common Test Design Challenges",
                        "duration": 35,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Solve Boundary and Equivalence Tasks",
                        "duration": 50,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                ),
            ),
            (
                "Practical Interview Tasks",
                (
                    {
                        "title": "Live Testing Case Strategies",
                        "duration": 35,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Complete a Timed Testing Exercise",
                        "duration": 50,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
            (
                "API and SQL Questions",
                (
                    {
                        "title": "Reasoning About APIs and Data",
                        "duration": 35,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Practice Technical Interview Questions",
                        "duration": 50,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                ),
            ),
            (
                "Mock Interview Preparation",
                (
                    {
                        "title": "Structuring Experience and Project Stories",
                        "duration": 35,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": False,
                    },
                    {
                        "title": "Mock Interview and Personal Action Plan",
                        "duration": 50,
                        "quiz": None,
                        "preview": False,
                        "unlock_after_days": None,
                        "resource": True,
                    },
                ),
            ),
        ),
    },
)

QUIZZES = {
    "testing-techniques": (
        (
            "single_choice",
            "What is Boundary Value Analysis?",
            [
                "Testing only typical values",
                "Testing values at and around boundaries",
                "Testing UI colors",
                "Testing without requirements",
            ],
            [1],
            None,
            "",
        ),
        (
            "true_false",
            "Equivalence partitioning groups inputs expected to behave similarly.",
            [],
            [],
            True,
            "",
        ),
    ),
    "fundamentals-final": (
        (
            "single_choice",
            "What is the main purpose of regression testing?",
            [
                "Confirm existing behavior still works after changes",
                "Measure server hardware",
                "Replace acceptance testing",
                "Write product requirements",
            ],
            [0],
            None,
            "",
        ),
        (
            "multiple_choice",
            "Which details make a bug report actionable?",
            [
                "Reproduction steps",
                "Expected and actual result",
                "Environment",
                "The reporter's job title",
            ],
            [0, 1, 2],
            None,
            "",
        ),
    ),
    "http-fundamentals": (
        (
            "single_choice",
            "Which HTTP status code usually indicates that a resource was not found?",
            ["200", "201", "404", "500"],
            [2],
            None,
            "",
        ),
        ("true_false", "A POST request is commonly used to create a resource.", [], [], True, ""),
    ),
    "api-scenarios": (
        (
            "multiple_choice",
            "Which checks belong in a useful API test?",
            ["Status code", "Response schema", "Business rules", "Monitor brightness"],
            [0, 1, 2],
            None,
            "",
        ),
        (
            "short_answer",
            "Name the HTTP header commonly used to send a bearer token.",
            [],
            [],
            None,
            "Authorization",
        ),
    ),
    "sql-filtering": (
        (
            "single_choice",
            "Which SQL clause is used to filter rows?",
            ["ORDER BY", "WHERE", "GROUP BY", "JOIN"],
            [1],
            None,
            "",
        ),
        (
            "short_answer",
            "Write the keyword used to retrieve columns from a table.",
            [],
            [],
            None,
            "SELECT",
        ),
    ),
    "sql-joins": (
        (
            "single_choice",
            "Which join returns only matching rows from both tables?",
            ["INNER JOIN", "LEFT JOIN", "CROSS JOIN", "FULL OUTER JOIN"],
            [0],
            None,
            "",
        ),
    ),
}
