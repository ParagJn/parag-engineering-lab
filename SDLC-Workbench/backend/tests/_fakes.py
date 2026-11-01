"""Secret-shaped test data, assembled at run time.

Nothing here is a string literal that looks like a secret: every value is joined from short fragments, so this file, like
every test file, contains no secret-shaped text. That matters because the repository is public, hosting services refuse
pushes that contain one, and a test (test_guardrails_repo.py) scans the whole project for exactly this.
"""
from __future__ import annotations


def join(*parts: str) -> str:
    return "".join(parts)


PRIVATE_KEY = join("-----", "BEGIN RSA PRIV", "ATE KEY-----")
AWS_KEY = join("AK", "IA", "ABCDEFGHIJKLMNOP")
AWS_TEMP_KEY = join("AS", "IA", "QRSTUVWXYZ012345")
GITHUB_TOKEN = join("gh", "p_", "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8")
GITHUB_FINE = join("github", "_pat_", "11ABCDEFG0abcdefghijkl_mnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQR")
SLACK_TOKEN = join("xo", "xb-", "1234567890-abcdefghij")
STRIPE_KEY = join("sk", "_live_", "abcdefghijklmnop1234")
STRIPE_RESTRICTED = join("rk", "_live_", "abcdefghijklmnop1234")
GOOGLE_KEY = join("AI", "za", "SyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q")
JWT = join("ey", "Jhbgci0iJIUzI1", ".", "eyJzdWIiOiIxMjM0NTY3", ".", "SflKxwRJSMeKKF2QT4fw")
URL_WITH_PASSWORD = join("postgres", "://admin:", "Tr0ub4dor", "@db.internal:5432/app")
ASSIGNED_SECRET = join("api_key = ", "Zk9", "xQ2mP7", "vR4tY8wL")
EMAIL = join("jane.doe", "@", "acme-corp.", "co.uk")
PHONE_INTL = "+44 20 7946 0958"
PHONE_US = join("(555) ", "123-", "4567")
CARD = join("4111", " ", "1111", " ", "1111", " ", "1111")
CARD_DASHED = join("4242", "-", "4242", "-", "4242", "-", "4242")
CARD_PLAIN = join("4111", "1111", "1111", "1111")
CARD_AMEX = join("3782", " ", "822463", " ", "10005")
IBAN = join("GB82", " WEST", " 1234", " 5698", " 7654", " 32")
CONFIGURED = join("configured-", "value-", "for-tests-77")

# (rule, text) for every rule: one value that must be found.
POSITIVE = {
    "private_key": PRIVATE_KEY,
    "aws_key_id": AWS_KEY,
    "github_token": GITHUB_TOKEN,
    "slack_token": SLACK_TOKEN,
    "stripe_key": STRIPE_KEY,
    "google_api_key": GOOGLE_KEY,
    "jwt": JWT,
    "url_password": URL_WITH_PASSWORD,
    "credential_assignment": ASSIGNED_SECRET,
    "email": join("contact ", EMAIL, " for help"),
    "phone": join("call ", PHONE_INTL, " today"),
    "payment_card": join("card ", CARD),
    "iban": join("pay to ", IBAN),
}

# Values a model, a person or a document could legitimately write. None of these may fire any rule.
CLEAN = [
    "- FR-001 The system shall refuse a booking. Derives from: PER-001, REQ-PRB-001 [DOC-001#1]",
    "Office hours are 08:00 to 18:00 on weekdays; ref 2026-10-29; v1.2.3; 1,395 tokens in / 1188 out; cost $0.01467",
    "contact support@example.com or admin@example.org or a@b.test or ops@service.invalid or me@localhost.local",
    join("postgres", "://user:password@host/db"), join("https", "://user:pass@host"), join("postgres", "://${DB_USER}:${DB_PASSWORD}@host/db"),
    "password: ${DB_PASSWORD}", "password = changeme", "password = <your-password>", "token: xxxxxxxxxxxx", "secret: {{ vault.secret }}",
    "the password policy requires at least twelve characters", "password: The booking rules apply to every member of staff",
    "api_key = YOUR_API_KEY_HERE", "api key: set in the environment", "token = REQ-F-001-REQ-F-002", "secret = aaaaaaaaaaaaaaaa",
    "uuid 123e4567-e89b-12d3-a456-426614174000", "sha 9fceb02d0ae598e95dc970b74767f19372d61af8", "call_id c3f9a1b2d4e5",
    "4111 1111 1111 1112 is not a card", "5555555555555555 is repeated digits", "call 555-123", "build 20261029 12345678",
    "order number 1234567890123", "GB82 WEST 1234 5698 7654 33", "Ref: GB-2026-000123", "version 12.34.56.78",
    "see https://example.com/docs and http://localhost:8090/api/status", "path /Users/someone/project/backend/app/main.py",
    "Sonnet 5.5 costs 2.00 per million input tokens and 10.00 per million output tokens", "lines 12-18 of page 3",
    "The reservation is held from 09:00 until 10:30 (UTC+1).", "tel: not provided", "email: not provided", "Staff can sign in with their company login.",
]
