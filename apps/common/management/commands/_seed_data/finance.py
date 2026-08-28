"""Orders, payments, refunds, and teacher payouts for the admin finance panel.

No provider is ever contacted: rows are written directly, mirroring the shape
`CheckoutService` produces. Provider identifiers are obviously fake on purpose
(`pi_seed_*`, `cs_test_seed_*`) so nobody mistakes them for live references.

Spread matters more than volume here. The finance summary compares two periods,
the timeseries buckets by day, week, and month, and revenue-by-category needs
payment items pointing at courses in different categories, so `days_ago` values
run across roughly two months and the courses span three categories.

Only LiqPay payments produce teacher ledger entries (Stripe settles through
Connect instead), which is why the payment method mix is deliberate.
"""

# `format` names a CourseDeliveryFormat.format_type on that course; the seeder
# resolves the PricingPlan and amount from it.
ORDER_SPECS = [
    {
        "key": "dj-001",
        "student": "kateryna.bondar@example.com",
        "course": "backend-engineering-django",
        "format": "group",
        "amount": "149.99",
        "currency": "USD",
        "status": "paid",
        "days_ago": 55,
        "payments": [
            {"amount": "149.99", "status": "succeeded", "method": "stripe", "days_ago": 55},
        ],
    },
    {
        "key": "dj-002",
        "student": "tomasz.wisniewski@example.com",
        "course": "backend-engineering-django",
        "format": "group",
        "amount": "160.00",
        "currency": "USD",
        "status": "partially_paid",
        "payment_type": "installments",
        "days_ago": 52,
        "installments": [
            {"number": 1, "amount": "40.00", "due_days_ago": 52, "status": "paid"},
            {"number": 2, "amount": "40.00", "due_days_ago": 22, "status": "paid"},
            # Deliberately overdue, so the order detail shows the overdue state.
            {"number": 3, "amount": "40.00", "due_days_ago": 4, "status": "pending"},
            {"number": 4, "amount": "40.00", "due_days_ago": -26, "status": "pending"},
        ],
        "payments": [
            {
                "amount": "40.00",
                "status": "succeeded",
                "method": "liqpay",
                "days_ago": 52,
                "installment": 1,
            },
            {
                "amount": "40.00",
                "status": "succeeded",
                "method": "liqpay",
                "days_ago": 22,
                "installment": 2,
            },
        ],
    },
    {
        "key": "dj-003",
        "student": "aisha.rahman@example.com",
        "course": "backend-engineering-django",
        "format": "individual",
        "amount": "299.00",
        "currency": "USD",
        "status": "paid",
        "days_ago": 45,
        "payments": [
            {"amount": "299.00", "status": "succeeded", "method": "liqpay", "days_ago": 45},
        ],
    },
    {
        "key": "dj-004",
        "student": "noah.callahan@example.com",
        "course": "backend-engineering-django",
        "format": "group",
        "amount": "149.99",
        "currency": "USD",
        "status": "failed",
        "days_ago": 40,
        "payments": [
            {
                "amount": "149.99",
                "status": "failed",
                "method": "stripe",
                "days_ago": 40,
                "error": "Your card was declined.",
            },
        ],
    },
    {
        "key": "dj-005",
        "student": "ibrahim.toure@example.com",
        "course": "backend-engineering-django",
        "format": "group",
        "amount": "149.99",
        "currency": "USD",
        "status": "refunded",
        "days_ago": 38,
        "payments": [
            {"amount": "149.99", "status": "refunded", "method": "stripe", "days_ago": 38},
        ],
        "refund": {
            "amount": "149.99",
            "days_ago": 30,
            "reason": "Requested within the 14-day window, no lessons completed.",
        },
    },
    {
        "key": "re-001",
        "student": "tomasz.wisniewski@example.com",
        "course": "react-from-scratch",
        "format": "self_paced",
        "amount": "120.00",
        "currency": "EUR",
        "status": "paid",
        "days_ago": 35,
        "payments": [
            {"amount": "120.00", "status": "succeeded", "method": "stripe", "days_ago": 35},
        ],
    },
    {
        "key": "re-002",
        "student": "lukas.berger@example.com",
        "course": "react-from-scratch",
        "format": "self_paced",
        "amount": "120.00",
        "currency": "EUR",
        "status": "paid",
        "days_ago": 28,
        "payments": [
            {"amount": "120.00", "status": "succeeded", "method": "liqpay", "days_ago": 28},
        ],
    },
    {
        "key": "ux-001",
        "student": "mariya.ivanenko@example.com",
        "course": "ux-design-fundamentals",
        "format": "group",
        "amount": "3000.00",
        "currency": "UAH",
        "status": "paid",
        "days_ago": 25,
        "payments": [
            {"amount": "3000.00", "status": "succeeded", "method": "liqpay", "days_ago": 25},
        ],
    },
    {
        "key": "ux-002",
        "student": "tomasz.wisniewski@example.com",
        "course": "ux-design-fundamentals",
        "format": "individual",
        "amount": "5500.00",
        "currency": "UAH",
        "status": "partially_paid",
        "payment_type": "installments",
        "days_ago": 60,
        "installments": [
            {"number": 1, "amount": "1100.00", "due_days_ago": 60, "status": "paid"},
            {"number": 2, "amount": "1100.00", "due_days_ago": 40, "status": "paid"},
            {"number": 3, "amount": "1100.00", "due_days_ago": 20, "status": "paid"},
            {"number": 4, "amount": "1100.00", "due_days_ago": -10, "status": "pending"},
            {"number": 5, "amount": "1100.00", "due_days_ago": -40, "status": "pending"},
        ],
        "payments": [
            {
                "amount": "1100.00",
                "status": "succeeded",
                "method": "liqpay",
                "days_ago": 60,
                "installment": 1,
            },
            {
                "amount": "1100.00",
                "status": "succeeded",
                "method": "liqpay",
                "days_ago": 40,
                "installment": 2,
            },
            {
                "amount": "1100.00",
                "status": "succeeded",
                "method": "liqpay",
                "days_ago": 20,
                "installment": 3,
            },
        ],
    },
    {
        "key": "da-001",
        "student": "aisha.rahman@example.com",
        "course": "data-analysis-bootcamp",
        "format": "group",
        "amount": "199.00",
        "currency": "USD",
        "status": "paid",
        "days_ago": 22,
        "payments": [
            {"amount": "199.00", "status": "succeeded", "method": "stripe", "days_ago": 22},
        ],
    },
    {
        "key": "da-002",
        "student": "lukas.berger@example.com",
        "course": "data-analysis-bootcamp",
        "format": "group",
        "amount": "199.00",
        "currency": "USD",
        "status": "paid",
        "days_ago": 18,
        "payments": [
            {"amount": "199.00", "status": "succeeded", "method": "stripe", "days_ago": 18},
        ],
        # Partial refund: the payment stays succeeded, which is what makes the
        # summary's partially_refunded counter non-zero.
        "refund": {
            "amount": "50.00",
            "days_ago": 12,
            "reason": "Goodwill refund after two cancelled live sessions.",
        },
    },
    {
        "key": "fs-001",
        "student": "noah.callahan@example.com",
        "course": "fullstack-javascript",
        "format": "self_paced",
        "amount": "99.00",
        "currency": "USD",
        "status": "paid",
        "days_ago": 15,
        "payments": [
            {"amount": "99.00", "status": "succeeded", "method": "liqpay", "days_ago": 15},
        ],
    },
    {
        "key": "fs-002",
        "student": "ibrahim.toure@example.com",
        "course": "fullstack-javascript",
        "format": "self_paced",
        "amount": "99.00",
        "currency": "USD",
        "status": "canceled",
        "days_ago": 14,
        "payments": [
            {"amount": "99.00", "status": "canceled", "method": "stripe", "days_ago": 14},
        ],
    },
    {
        "key": "re-004",
        "student": "kateryna.bondar@example.com",
        "course": "react-from-scratch",
        "format": "self_paced",
        "amount": "120.00",
        "currency": "EUR",
        "status": "paid",
        "days_ago": 10,
        "payments": [
            {"amount": "120.00", "status": "succeeded", "method": "stripe", "days_ago": 10},
        ],
    },
    {
        "key": "da-003",
        "student": "mariya.ivanenko@example.com",
        "course": "data-analysis-bootcamp",
        "format": "group",
        "amount": "199.00",
        "currency": "USD",
        "status": "failed",
        "days_ago": 8,
        "payments": [
            {
                "amount": "199.00",
                "status": "failed",
                "method": "stripe",
                "days_ago": 8,
                "error": "Insufficient funds.",
            },
        ],
    },
    {
        "key": "ux-003",
        "student": "lukas.berger@example.com",
        "course": "ux-design-fundamentals",
        "format": "group",
        "amount": "3000.00",
        "currency": "UAH",
        "status": "paid",
        "days_ago": 6,
        "payments": [
            {"amount": "3000.00", "status": "succeeded", "method": "stripe", "days_ago": 6},
        ],
    },
    {
        "key": "fs-003",
        "student": "tomasz.wisniewski@example.com",
        "course": "fullstack-javascript",
        "format": "self_paced",
        "amount": "99.00",
        "currency": "USD",
        "status": "canceled",
        "days_ago": 5,
        "payments": [
            {"amount": "99.00", "status": "canceled", "method": "stripe", "days_ago": 5},
        ],
    },
    {
        "key": "dj-007",
        "student": "mariya.ivanenko@example.com",
        "course": "backend-engineering-django",
        "format": "individual",
        "amount": "299.00",
        "currency": "USD",
        "status": "paid",
        "days_ago": 4,
        "payments": [
            {"amount": "299.00", "status": "succeeded", "method": "liqpay", "days_ago": 4},
        ],
    },
    {
        "key": "re-003",
        "student": "julia.novak@example.com",
        "course": "react-from-scratch",
        "format": "self_paced",
        "amount": "120.00",
        "currency": "EUR",
        "status": "pending",
        "days_ago": 3,
        "payments": [
            {"amount": "120.00", "status": "pending", "method": "stripe", "days_ago": 3},
        ],
    },
    {
        "key": "dj-006",
        "student": "julia.novak@example.com",
        "course": "backend-engineering-django",
        "format": "group",
        "amount": "149.99",
        "currency": "USD",
        "status": "pending",
        "days_ago": 2,
        "payments": [
            {"amount": "149.99", "status": "processing", "method": "stripe", "days_ago": 2},
        ],
    },
    {
        "key": "re-005",
        "student": "aisha.rahman@example.com",
        "course": "react-from-scratch",
        "format": "self_paced",
        "amount": "120.00",
        "currency": "EUR",
        "status": "failed",
        "days_ago": 1,
        "payments": [
            {
                "amount": "120.00",
                "status": "failed",
                "method": "stripe",
                "days_ago": 1,
                "error": "Authentication required, 3D Secure was not completed.",
            },
        ],
    },
    {
        "key": "da-004",
        "student": "julia.novak@example.com",
        "course": "data-analysis-bootcamp",
        "format": "group",
        "amount": "199.00",
        "currency": "USD",
        "status": "pending",
        "days_ago": 1,
        "payments": [
            {"amount": "199.00", "status": "processing", "method": "liqpay", "days_ago": 1},
        ],
    },
]

# One payout destination and one settled payout per teacher who has LiqPay
# earnings, so the staff finance screens are not empty.
PAYOUT_SPECS = [
    {
        "teacher": "andrii.melnyk@example.com",
        "destination": {
            "destination_type": "bank_account",
            "receiver_account": "UA213223130000026007233566001",
            "receiver_mfo": "322313",
            "receiver_okpo": "38736443",
            "receiver_company": "Andrii Melnyk FOP",
        },
        "payouts": [
            {"key": "payout-teacher1-1", "amount": "400.00", "currency": "USD", "days_ago": 12},
        ],
    },
    {
        "teacher": "daniel.okonkwo@example.com",
        "destination": {
            "destination_type": "bank_account",
            "receiver_account": "UA903052990000026001234567897",
            "receiver_mfo": "305299",
            "receiver_okpo": "41229035",
            "receiver_company": "Daniel Okonkwo FOP",
        },
        "payouts": [
            {"key": "payout-teacher3-1", "amount": "4000.00", "currency": "UAH", "days_ago": 9},
        ],
    },
]
