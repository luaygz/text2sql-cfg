"""Hand-written parameters of the synthetic world: seed, snapshot date, tenants and text pools.

The generator draws everything else from these with one seeded RNG, so changing any value here
changes the database (and its SHA-256) on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SAAS_SEED = 20261016

AS_OF = date(2026, 9, 30)
"""Snapshot date. Organic rows are dated strictly before it; planted injection rows on it."""

LEGACY_BILLING_CUTOVER = date(2024, 7, 1)
"""Invoices issued before this date were imported from a legacy system (US-format due dates)."""


@dataclass(frozen=True, slots=True)
class TenantProfile:
    tenant_id: int
    name: str
    domain: str
    country_code: str
    currency_code: str
    signed_up: date
    accounts: int
    """Organic accounts to generate (canary and planted rows come on top)."""
    annual_share: float
    """Probability that a new subscription is billed annually rather than monthly."""


TENANTS: tuple[TenantProfile, ...] = (
    TenantProfile(
        1,
        "Northwind Analytics",
        "northwind-analytics.example",
        "US",
        "USD",
        date(2023, 1, 9),
        200,
        0.35,
    ),
    TenantProfile(
        2, "Brightline Logistics", "brightline.example", "GB", "GBP", date(2023, 2, 20), 140, 0.5
    ),
    TenantProfile(
        3, "Kestrel Health", "kestrelhealth.example", "US", "USD", date(2023, 4, 3), 110, 0.6
    ),
    TenantProfile(
        4, "Alpenglow Software GmbH", "alpenglow.example", "DE", "EUR", date(2023, 6, 12), 90, 0.45
    ),
    TenantProfile(
        5, "Maple & Pine Supply", "mapleandpine.example", "CA", "CAD", date(2023, 9, 18), 70, 0.3
    ),
    TenantProfile(
        6, "Harbor Point Media", "harborpoint.example", "AU", "AUD", date(2024, 1, 22), 50, 0.4
    ),
    TenantProfile(
        7, "Solstice Energy", "solstice-energy.example", "US", "USD", date(2024, 5, 6), 120, 0.55
    ),
    TenantProfile(8, "Lumen Legal", "lumenlegal.example", "FR", "EUR", date(2024, 11, 11), 40, 0.5),
)

# Customer names that most tenants share, so an answer that mixes tenants is visibly wrong.
SHARED_ACCOUNT_NAMES: tuple[str, ...] = (
    "Acme Logistics",
    "Bluewater Foods",
    "Cedar Ridge Health",
    "Summit Analytics",
    "Northstar Freight",
    "Ironwood Manufacturing",
    "Pioneer Dental Group",
    "Riverbend Credit Union",
    "Silverline Media",
    "Oakmont Realty",
    "Brightpath Learning",
    "Granite Peak Energy",
    "Harborview Hotels",
    "Evergreen Legal",
    "Redwood Retail",
    "Clearwater Telecom",
    "Falcon Robotics",
    "Golden Gate Insurance",
    "Lakeside Clinics",
    "Metro Transit Supply",
    "Orion Biotech",
    "Quantum Payments",
    "Starlight Events",
    "Westfield Construction",
)
SHARED_NAME_PROBABILITY = 0.65
GENERATED_NAME_POOL = 320

COMPANY_SUFFIXES: tuple[str, ...] = (
    "Logistics",
    "Health",
    "Systems",
    "Partners",
    "Group",
    "Labs",
    "Foods",
    "Energy",
    "Capital",
    "Media",
    "Retail",
    "Holdings",
    "Consulting",
    "Manufacturing",
    "Clinics",
    "Software",
)

SALES_TEAM_NAMES: tuple[str, ...] = ("Sales East", "Sales West", "Enterprise Sales")

JOB_TITLES: tuple[str, ...] = (
    "CEO",
    "CFO",
    "CTO",
    "COO",
    "VP of Sales",
    "VP of Operations",
    "Head of Finance",
    "IT Manager",
    "Procurement Specialist",
    "Finance Manager",
    "Office Manager",
    "Director of Engineering",
    "Customer Success Lead",
    "Controller",
    "Marketing Manager",
    "Data Analyst",
    "Operations Manager",
    "Head of People",
)

LEAD_SOURCES: tuple[str, ...] = ("inbound", "outbound", "referral", "partner", "event")

TICKET_SUBJECTS: tuple[str, ...] = (
    "Cannot log in with SSO",
    "CSV export times out",
    "Dashboard shows wrong totals",
    "Question about our latest invoice",
    "Need to add {seats} more seats",
    "Webhook deliveries failing",
    "Change billing contact",
    "API returns 429 rate limit errors",
    "Scheduled report emails not arriving",
    "Request to delete a former employee's data",
    "Calendar sync stopped working",
    "Password reset email not received",
    "How do we change our plan?",
    "Duplicate contacts after import",
    "Mobile app crashes on startup",
    "Custom field missing from report",
    "Card payment declined",
)

ACTIVITY_SUBJECTS: dict[str, tuple[str, ...]] = {
    "call": (
        "Intro call",
        "Discovery call",
        "Follow-up call",
        "Pricing discussion",
        "Check-in call",
    ),
    "email": (
        "Sent proposal",
        "Sent pricing sheet",
        "Follow-up email",
        "Shared case study",
        "Renewal reminder",
    ),
    "meeting": (
        "Quarterly business review",
        "On-site visit",
        "Kickoff meeting",
        "Executive sponsor meeting",
    ),
    "demo": ("Product demo", "Reporting module demo", "Billing module demo"),
    "note": (
        "Account note",
        "Competitor mentioned",
        "Budget approved for next quarter",
        "Champion left the company",
    ),
}

SERVICES: tuple[tuple[str, float], ...] = (
    ("Onboarding package", 2500.0),
    ("Data migration", 4000.0),
    ("Custom training (half day)", 1200.0),
    ("Premium support add-on", 1800.0),
)
"""One-off services billed outside subscriptions: (line description, USD price)."""
