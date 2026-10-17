"""Global reference rows: currencies, countries, industries and the shared plan price list.

These tables have no tenant column; every tenant reads the same rows. Exchange and tax rates are
fixed illustrative values chosen for the synthetic data, not market data or tax advice.
"""

from __future__ import annotations

from dataclasses import dataclass

type RefRow = tuple[str | int | float | None, ...]


@dataclass(frozen=True, slots=True)
class Plan:
    plan_id: int
    name: str
    tier: str
    billing_period: str
    price_per_seat: float
    """USD per seat per billing period."""
    max_seats: int | None
    is_active: bool

    @property
    def months(self) -> int:
        return 12 if self.billing_period == "annual" else 1

    def as_row(self) -> RefRow:
        return (
            self.plan_id,
            self.name,
            self.tier,
            self.billing_period,
            self.price_per_seat,
            self.max_seats,
            int(self.is_active),
        )


CURRENCIES: tuple[RefRow, ...] = (
    ("USD", "US Dollar", "$", 1.0),
    ("EUR", "Euro", "€", 1.1),
    ("GBP", "Pound Sterling", "£", 1.3),
    ("CAD", "Canadian Dollar", "CA$", 0.73),
    ("AUD", "Australian Dollar", "A$", 0.66),
    ("CHF", "Swiss Franc", "CHF", 1.15),
    ("SEK", "Swedish Krona", "kr", 0.095),
    ("SGD", "Singapore Dollar", "S$", 0.75),
)
USD_RATE: dict[str, float] = {str(row[0]): float(row[3] or 0) for row in CURRENCIES}

COUNTRIES: tuple[RefRow, ...] = (
    ("US", "United States", "North America", "USD"),
    ("CA", "Canada", "North America", "CAD"),
    ("GB", "United Kingdom", "Europe", "GBP"),
    ("IE", "Ireland", "Europe", "EUR"),
    ("DE", "Germany", "Europe", "EUR"),
    ("FR", "France", "Europe", "EUR"),
    ("NL", "Netherlands", "Europe", "EUR"),
    ("ES", "Spain", "Europe", "EUR"),
    ("IT", "Italy", "Europe", "EUR"),
    ("BE", "Belgium", "Europe", "EUR"),
    ("AT", "Austria", "Europe", "EUR"),
    ("SE", "Sweden", "Europe", "SEK"),
    ("CH", "Switzerland", "Europe", "CHF"),
    ("AU", "Australia", "Asia Pacific", "AUD"),
    ("SG", "Singapore", "Asia Pacific", "SGD"),
)
COUNTRY_REGION: dict[str, str] = {str(row[0]): str(row[2]) for row in COUNTRIES}
COUNTRY_CURRENCY: dict[str, str] = {str(row[0]): str(row[3]) for row in COUNTRIES}

# Domestic sales tax applied by a tenant to customers in its own country; cross-border B2B
# invoices carry no tax. Illustrative rates only.
DOMESTIC_TAX_RATE: dict[str, float] = {
    "US": 0.0,
    "CA": 0.05,
    "GB": 0.2,
    "DE": 0.19,
    "FR": 0.2,
    "AU": 0.1,
}

INDUSTRIES: tuple[RefRow, ...] = (
    (1, "Software", "Technology"),
    (2, "Telecommunications", "Technology"),
    (3, "Financial Services", "Finance"),
    (4, "Insurance", "Finance"),
    (5, "Healthcare", "Health"),
    (6, "Biotechnology", "Health"),
    (7, "Manufacturing", "Industrial"),
    (8, "Logistics", "Industrial"),
    (9, "Energy", "Industrial"),
    (10, "Retail", "Consumer"),
    (11, "Hospitality", "Consumer"),
    (12, "Media", "Consumer"),
    (13, "Education", "Public Sector"),
    (14, "Government", "Public Sector"),
    (15, "Legal Services", "Professional Services"),
    (16, "Real Estate", "Professional Services"),
)

PLANS: tuple[Plan, ...] = (
    Plan(1, "Starter (monthly)", "starter", "monthly", 15.0, 10, True),
    Plan(2, "Starter (annual)", "starter", "annual", 150.0, 10, True),
    Plan(3, "Growth (monthly)", "growth", "monthly", 35.0, 50, True),
    Plan(4, "Growth (annual)", "growth", "annual", 350.0, 50, True),
    Plan(5, "Business (monthly)", "business", "monthly", 65.0, 250, True),
    Plan(6, "Business (annual)", "business", "annual", 650.0, 250, True),
    Plan(7, "Enterprise (annual)", "enterprise", "annual", 1100.0, None, True),
    Plan(8, "Pro (legacy, monthly)", "legacy", "monthly", 25.0, 25, False),
)
