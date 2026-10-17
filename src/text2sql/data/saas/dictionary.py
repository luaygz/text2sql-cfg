"""Data dictionary of the SaaS CRM database: one declaration per table and column.

Each `ColumnSpec` drives the CREATE TABLE statement the generator runs, the description the
model reads, and (through `TableSpec.scope` and `ColumnSpec.sensitive`) the scope policy, so the
three cannot drift apart. Descriptions are written for the model: they never mention the tenant
column, which the model must not see or produce.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from text2sql.catalog.schema import Column, DatabaseSchema, Table, introspect_sqlite
from text2sql.config import REPO_ROOT

SAAS_DB_ID = "saas_crm"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "saas" / "crm.sqlite"

Scope = Literal["global", "tenant", "owner"]
"""global: shared reference data; tenant: has tenant_id; owner: tenant_id plus owner_user_id."""


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    name: str
    type: str
    description: str
    value_description: str | None = None
    nullable: bool = False
    primary_key: bool = False
    references: tuple[str, str] | None = None
    sensitive: bool = False
    """Secret material the model must never see (hidden by the scope policy)."""


@dataclass(frozen=True, slots=True)
class TableSpec:
    name: str
    scope: Scope
    description: str
    columns: tuple[ColumnSpec, ...]

    def column(self, name: str) -> ColumnSpec | None:
        return next((c for c in self.columns if c.name == name), None)


def _pk(name: str, description: str, type_: str = "INTEGER") -> ColumnSpec:
    return ColumnSpec(name, type_, description, primary_key=True)


def _tenant() -> ColumnSpec:
    return ColumnSpec(
        "tenant_id",
        "INTEGER",
        "Organisation that owns the row. Hidden from the model; the scoping layer adds the filter.",
        references=("tenants", "tenant_id"),
    )


def _owner(description: str) -> ColumnSpec:
    return ColumnSpec("owner_user_id", "INTEGER", description, references=("users", "user_id"))


def _created(description: str = "When the row was created.") -> ColumnSpec:
    return ColumnSpec("created_at", "TEXT", description, "Text 'YYYY-MM-DD HH:MM:SS' (UTC).")


_CASING = "Casing is inconsistent ({examples}); compare with LOWER()."

TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        "currencies",
        "global",
        "Currencies used for prices, deals, invoices and payments.",
        (
            _pk("currency_code", "ISO 4217 code, e.g. 'USD'.", "TEXT"),
            ColumnSpec("name", "TEXT", "Currency name."),
            ColumnSpec("symbol", "TEXT", "Display symbol, e.g. '$'."),
            ColumnSpec(
                "usd_rate",
                "REAL",
                "US dollars per one unit of this currency.",
                "Fixed reporting rate. Multiply a major-unit amount by it to convert to USD.",
            ),
        ),
    ),
    TableSpec(
        "countries",
        "global",
        "Countries that accounts and organisations are based in.",
        (
            _pk("country_code", "ISO 3166-1 alpha-2 code, e.g. 'DE'.", "TEXT"),
            ColumnSpec("name", "TEXT", "Country name."),
            ColumnSpec(
                "region",
                "TEXT",
                "Sales region.",
                "One of 'North America', 'Europe', 'Asia Pacific'.",
            ),
            ColumnSpec(
                "currency_code",
                "TEXT",
                "Local currency.",
                references=("currencies", "currency_code"),
            ),
        ),
    ),
    TableSpec(
        "industries",
        "global",
        "Industry classification for accounts.",
        (
            _pk("industry_id", "Industry identifier."),
            ColumnSpec("name", "TEXT", "Industry name, e.g. 'Logistics'."),
            ColumnSpec(
                "sector",
                "TEXT",
                "Broader sector grouping several industries.",
                "One of 'Technology', 'Finance', 'Health', 'Industrial', 'Consumer', "
                "'Public Sector', 'Professional Services'.",
            ),
        ),
    ),
    TableSpec(
        "plans",
        "global",
        "Standard subscription plans: the shared price list.",
        (
            _pk("plan_id", "Plan identifier."),
            ColumnSpec("name", "TEXT", "Plan name, e.g. 'Growth (annual)'."),
            ColumnSpec(
                "tier",
                "TEXT",
                "Plan tier.",
                "One of 'starter', 'growth', 'business', 'enterprise', 'legacy'.",
            ),
            ColumnSpec(
                "billing_period",
                "TEXT",
                "How often the plan is invoiced.",
                "'monthly' or 'annual'.",
            ),
            ColumnSpec(
                "price_per_seat",
                "REAL",
                "List price in USD per seat per billing period.",
                "A monthly plan bills this every month, an annual plan once a year.",
            ),
            ColumnSpec(
                "max_seats",
                "INTEGER",
                "Most seats a subscription on this plan may have.",
                "NULL means unlimited.",
                nullable=True,
            ),
            ColumnSpec(
                "is_active",
                "INTEGER",
                "Whether the plan can still be sold.",
                "1 = on sale; 0 = retired, but existing subscriptions may still use it.",
            ),
        ),
    ),
    TableSpec(
        "tenants",
        "tenant",
        "The caller's own organisation (the company using this CRM). "
        "Queries only ever see one row: the caller's.",
        (
            _pk("tenant_id", "Organisation identifier. Hidden from the model."),
            ColumnSpec("name", "TEXT", "Organisation name."),
            ColumnSpec(
                "country_code",
                "TEXT",
                "Headquarters country.",
                "Customers in the same country are charged domestic sales tax.",
                references=("countries", "country_code"),
            ),
            ColumnSpec(
                "default_currency_code",
                "TEXT",
                "Currency most accounts are billed in.",
                references=("currencies", "currency_code"),
            ),
            ColumnSpec(
                "signed_up_at",
                "TEXT",
                "When the organisation started using the product.",
                "Text 'YYYY-MM-DD HH:MM:SS' (UTC).",
            ),
            ColumnSpec("api_key", "TEXT", "Secret API key of the organisation.", sensitive=True),
        ),
    ),
    TableSpec(
        "teams",
        "tenant",
        "Groups of users: sales regions, support, customer success.",
        (
            _pk("team_id", "Team identifier."),
            _tenant(),
            ColumnSpec("name", "TEXT", "Team name, e.g. 'Sales East'."),
            ColumnSpec(
                "department",
                "TEXT",
                "Department the team belongs to.",
                "One of 'sales', 'support', 'success'.",
            ),
        ),
    ),
    TableSpec(
        "users",
        "tenant",
        "People at the organisation who use the CRM: administrators, "
        "managers, sales reps, support agents and customer success managers.",
        (
            _pk("user_id", "User identifier."),
            _tenant(),
            ColumnSpec(
                "team_id",
                "INTEGER",
                "Team the user belongs to.",
                "NULL for administrators outside any team.",
                nullable=True,
                references=("teams", "team_id"),
            ),
            ColumnSpec(
                "manager_user_id",
                "INTEGER",
                "The user's manager (users.user_id).",
                "NULL for the top administrator.",
                nullable=True,
                references=("users", "user_id"),
            ),
            ColumnSpec("full_name", "TEXT", "First and last name."),
            ColumnSpec("email", "TEXT", "Work email address."),
            ColumnSpec(
                "role",
                "TEXT",
                "Job role in the CRM.",
                "One of 'admin', 'manager', 'sales_rep', 'support_agent', 'csm' "
                "(customer success manager).",
            ),
            ColumnSpec(
                "is_active",
                "INTEGER",
                "Whether the person still works there.",
                "1 = active; 0 = left the company. Records they owned keep pointing at them.",
            ),
            _created("When the user was added."),
            ColumnSpec(
                "last_login_at",
                "TEXT",
                "Most recent login.",
                "Text 'YYYY-MM-DD HH:MM:SS' (UTC); NULL if the user never logged in.",
                nullable=True,
            ),
            ColumnSpec("password_hash", "TEXT", "Password hash.", sensitive=True),
        ),
    ),
    TableSpec(
        "accounts",
        "owner",
        "Companies the organisation sells to: prospects, customers, former customers and partners.",
        (
            _pk("account_id", "Account identifier."),
            _tenant(),
            _owner("Account manager responsible for the account (users.user_id)."),
            ColumnSpec(
                "parent_account_id",
                "INTEGER",
                "Parent company of a subsidiary account.",
                "NULL for independent accounts.",
                nullable=True,
                references=("accounts", "account_id"),
            ),
            ColumnSpec(
                "name",
                "TEXT",
                "Company name as typed by users.",
                _CASING.format(examples="'Acme Logistics' vs 'ACME LOGISTICS'"),
            ),
            ColumnSpec(
                "industry_id",
                "INTEGER",
                "Industry of the company.",
                "NULL if unknown.",
                nullable=True,
                references=("industries", "industry_id"),
            ),
            ColumnSpec(
                "country_code",
                "TEXT",
                "Country the company is based in.",
                "NULL if unknown.",
                nullable=True,
                references=("countries", "country_code"),
            ),
            ColumnSpec(
                "currency_code",
                "TEXT",
                "Currency the account is quoted and billed in.",
                references=("currencies", "currency_code"),
            ),
            ColumnSpec(
                "lifecycle_stage",
                "TEXT",
                "Relationship stage.",
                "Values prospect, customer, churned (former customer), partner. "
                + _CASING.format(examples="'Customer', 'customer', 'CUSTOMER'"),
            ),
            ColumnSpec(
                "employee_count",
                "INTEGER",
                "Approximate head count of the company.",
                "NULL if unknown.",
                nullable=True,
            ),
            ColumnSpec(
                "website", "TEXT", "Company website domain.", "NULL if unknown.", nullable=True
            ),
            ColumnSpec(
                "payment_terms_days",
                "INTEGER",
                "Days between an invoice's issue date and its due date.",
                "15, 30 or 45.",
            ),
            _created("When the account was added to the CRM."),
        ),
    ),
    TableSpec(
        "contacts",
        "owner",
        "People at accounts.",
        (
            _pk("contact_id", "Contact identifier."),
            _tenant(),
            _owner("User responsible for the contact (users.user_id)."),
            ColumnSpec(
                "account_id",
                "INTEGER",
                "Company the contact works for.",
                references=("accounts", "account_id"),
            ),
            ColumnSpec("first_name", "TEXT", "First name."),
            ColumnSpec("last_name", "TEXT", "Last name."),
            ColumnSpec(
                "email",
                "TEXT",
                "Email address.",
                "Casing is inconsistent; compare with LOWER(). NULL if unknown.",
                nullable=True,
            ),
            ColumnSpec(
                "phone", "TEXT", "Phone number in free format.", "NULL if unknown.", nullable=True
            ),
            ColumnSpec(
                "job_title",
                "TEXT",
                "Job title as typed by users.",
                "Free text with inconsistent casing and stray spaces; compare with "
                "LOWER(TRIM(job_title)). NULL if unknown.",
                nullable=True,
            ),
            ColumnSpec(
                "is_primary",
                "INTEGER",
                "Whether this is the main contact of the account.",
                "1 for exactly one contact per account, else 0.",
            ),
            _created("When the contact was added."),
        ),
    ),
    TableSpec(
        "deals",
        "owner",
        "Sales opportunities. Every won deal (stage 'closed_won') "
        "started the subscription that references it.",
        (
            _pk("deal_id", "Deal identifier."),
            _tenant(),
            _owner("Sales rep who owns the deal (users.user_id)."),
            ColumnSpec(
                "account_id",
                "INTEGER",
                "Account the deal is with.",
                references=("accounts", "account_id"),
            ),
            ColumnSpec("name", "TEXT", "Deal name."),
            ColumnSpec(
                "stage",
                "TEXT",
                "Pipeline stage.",
                "Open: 'prospecting', 'qualification', 'proposal', 'negotiation'. "
                "Closed: 'closed_won', 'closed_lost'.",
            ),
            ColumnSpec(
                "amount",
                "REAL",
                "Expected first-year contract value.",
                "In the deal currency, major units (dollars, not cents).",
            ),
            ColumnSpec(
                "currency_code",
                "TEXT",
                "Currency of amount.",
                references=("currencies", "currency_code"),
            ),
            ColumnSpec(
                "probability",
                "INTEGER",
                "Rep's win probability in percent (0-100).",
                "NULL if the rep did not set it.",
                nullable=True,
            ),
            ColumnSpec(
                "lead_source",
                "TEXT",
                "Where the deal came from.",
                "One of 'inbound', 'outbound', 'referral', 'partner', 'event'; NULL if unknown.",
                nullable=True,
            ),
            ColumnSpec(
                "expected_close_date",
                "TEXT",
                "Date the rep forecasts the deal to close.",
                "Text 'YYYY-MM-DD'. Set for every deal; for closed deals it is the last "
                "forecast, not the actual close date (see closed_at).",
            ),
            _created("When the deal was opened."),
            ColumnSpec(
                "closed_at",
                "TEXT",
                "When the deal was actually won or lost.",
                "Text 'YYYY-MM-DD HH:MM:SS' (UTC); NULL while the deal is open.",
                nullable=True,
            ),
        ),
    ),
    TableSpec(
        "subscriptions",
        "owner",
        "Recurring plan subscriptions of accounts.",
        (
            _pk("subscription_id", "Subscription identifier."),
            _tenant(),
            _owner("Account manager of the subscribing account (same as accounts.owner_user_id)."),
            ColumnSpec(
                "account_id",
                "INTEGER",
                "Subscribing account.",
                references=("accounts", "account_id"),
            ),
            ColumnSpec(
                "plan_id", "INTEGER", "Plan subscribed to.", references=("plans", "plan_id")
            ),
            ColumnSpec(
                "deal_id",
                "INTEGER",
                "Won deal that created the subscription.",
                "NULL for self-serve sign-ups.",
                nullable=True,
                references=("deals", "deal_id"),
            ),
            ColumnSpec(
                "status",
                "TEXT",
                "Subscription state.",
                "One of 'trialing', 'active', 'past_due' (latest invoice overdue), 'canceled'.",
            ),
            ColumnSpec("seats", "INTEGER", "Number of licensed seats."),
            ColumnSpec("discount_pct", "REAL", "Discount off the list price, in percent (0-30)."),
            ColumnSpec(
                "currency_code",
                "TEXT",
                "Currency the subscription is billed in.",
                references=("currencies", "currency_code"),
            ),
            ColumnSpec(
                "started_at", "TEXT", "First day of the subscription.", "Text 'YYYY-MM-DD'."
            ),
            ColumnSpec(
                "canceled_at",
                "TEXT",
                "Day the subscription ended.",
                "Text 'YYYY-MM-DD'; NULL unless status is 'canceled'.",
                nullable=True,
            ),
        ),
    ),
    TableSpec(
        "invoices",
        "owner",
        "Invoices sent to accounts, for subscriptions or one-off services.",
        (
            _pk("invoice_id", "Invoice identifier."),
            _tenant(),
            _owner("Account manager of the invoiced account (same as accounts.owner_user_id)."),
            ColumnSpec(
                "account_id", "INTEGER", "Invoiced account.", references=("accounts", "account_id")
            ),
            ColumnSpec(
                "subscription_id",
                "INTEGER",
                "Subscription being billed.",
                "NULL for one-off services invoices.",
                nullable=True,
                references=("subscriptions", "subscription_id"),
            ),
            ColumnSpec(
                "invoice_number",
                "TEXT",
                "Invoice number shown to the customer.",
                "Format 'INV-YYYY-NNNNN'; numbering restarts every year.",
            ),
            ColumnSpec(
                "status",
                "TEXT",
                "Payment state.",
                "One of 'open' (unpaid; overdue once the due date has passed), 'paid', "
                "'void' (cancelled, never payable), 'uncollectible' (written off).",
            ),
            ColumnSpec(
                "currency_code",
                "TEXT",
                "Invoice currency.",
                references=("currencies", "currency_code"),
            ),
            ColumnSpec(
                "issued_at",
                "TEXT",
                "Issue date (start of the billed period).",
                "Text 'YYYY-MM-DD'.",
            ),
            ColumnSpec(
                "due_date",
                "TEXT",
                "Date payment is due.",
                "Text in two formats: 'YYYY-MM-DD' for invoices issued from 2024-07-01, "
                "'MM/DD/YYYY' for older invoices imported from the legacy billing system. "
                "Normalise before comparing or sorting, e.g. "
                "CASE WHEN INSTR(due_date, '/') > 0 THEN SUBSTR(due_date, 7, 4) || '-' || "
                "SUBSTR(due_date, 1, 2) || '-' || SUBSTR(due_date, 4, 2) ELSE due_date END.",
            ),
            ColumnSpec(
                "subtotal",
                "REAL",
                "Sum of the line items before tax.",
                "Invoice currency, major units.",
            ),
            ColumnSpec(
                "tax",
                "REAL",
                "Sales tax.",
                "Invoice currency, major units; 0 for customers outside the organisation's "
                "country.",
            ),
            ColumnSpec(
                "total_amount",
                "REAL",
                "Amount payable: subtotal plus tax.",
                "Invoice currency, major units (1234.50 means 1,234.50 dollars or euros).",
            ),
        ),
    ),
    TableSpec(
        "invoice_line_items",
        "owner",
        "Lines of an invoice.",
        (
            _pk("line_item_id", "Line item identifier."),
            _tenant(),
            _owner("Account manager of the invoiced account (same as invoices.owner_user_id)."),
            ColumnSpec(
                "invoice_id",
                "INTEGER",
                "Invoice the line belongs to.",
                references=("invoices", "invoice_id"),
            ),
            ColumnSpec("description", "TEXT", "Line text, e.g. the plan, period and seat count."),
            ColumnSpec("quantity", "INTEGER", "Units billed (seats for subscription lines)."),
            ColumnSpec(
                "unit_price",
                "REAL",
                "Price per unit.",
                "Invoice currency, major units; negative on discount lines.",
            ),
            ColumnSpec(
                "line_total", "REAL", "quantity * unit_price.", "Invoice currency, major units."
            ),
        ),
    ),
    TableSpec(
        "payments",
        "owner",
        "Payment attempts against invoices, as reported by the payment processor.",
        (
            _pk("payment_id", "Payment identifier."),
            _tenant(),
            _owner("Account manager of the paying account (same as invoices.owner_user_id)."),
            ColumnSpec(
                "invoice_id",
                "INTEGER",
                "Invoice being paid.",
                references=("invoices", "invoice_id"),
            ),
            ColumnSpec(
                "amount",
                "INTEGER",
                "Amount of the payment attempt in CENTS.",
                "Minor currency units as sent by the payment processor, unlike every other "
                "money column: 123450 means 1,234.50. Divide by 100.0 before comparing with "
                "invoices.total_amount or reporting money.",
            ),
            ColumnSpec(
                "currency_code",
                "TEXT",
                "Payment currency (same as the invoice).",
                references=("currencies", "currency_code"),
            ),
            ColumnSpec(
                "method",
                "TEXT",
                "Payment method.",
                "One of 'card', 'ach', 'sepa_debit', 'bacs', 'wire', 'check'.",
            ),
            ColumnSpec(
                "status",
                "TEXT",
                "Outcome of the attempt.",
                "'succeeded' (money received), 'failed', 'pending' (not settled yet). "
                "Only succeeded payments count as collected.",
            ),
            ColumnSpec(
                "paid_at",
                "TEXT",
                "When the payment was attempted.",
                "Text 'YYYY-MM-DD HH:MM:SS' (UTC).",
            ),
            ColumnSpec("processor_ref", "TEXT", "Reference id at the payment processor."),
        ),
    ),
    TableSpec(
        "tickets",
        "owner",
        "Customer support tickets.",
        (
            _pk("ticket_id", "Ticket identifier."),
            _tenant(),
            _owner("Support agent assigned to the ticket (users.user_id)."),
            ColumnSpec(
                "account_id",
                "INTEGER",
                "Account that raised the ticket.",
                references=("accounts", "account_id"),
            ),
            ColumnSpec(
                "contact_id",
                "INTEGER",
                "Contact who raised the ticket.",
                "NULL if not recorded.",
                nullable=True,
                references=("contacts", "contact_id"),
            ),
            ColumnSpec("subject", "TEXT", "Subject line written by the customer."),
            ColumnSpec(
                "description",
                "TEXT",
                "First message of the ticket.",
                "NULL if empty.",
                nullable=True,
            ),
            ColumnSpec(
                "priority",
                "TEXT",
                "Urgency.",
                "Values low, normal, high, urgent. "
                + _CASING.format(examples="'high', 'High', 'HIGH'"),
            ),
            ColumnSpec(
                "status",
                "TEXT",
                "Ticket state.",
                "One of 'open', 'pending' (waiting on the customer), 'solved', 'closed'.",
            ),
            ColumnSpec(
                "channel",
                "TEXT",
                "How the ticket arrived.",
                "One of 'email', 'web', 'chat', 'phone', 'api'.",
            ),
            ColumnSpec(
                "opened_at",
                "TEXT",
                "When the ticket was opened.",
                "Text in two formats: 'YYYY-MM-DDTHH:MM:SSZ' for channel 'web' and 'api', "
                "'YYYY-MM-DD HH:MM:SS' otherwise (both UTC). Plain text comparison misorders "
                "the two formats within a day: sort and compare with JULIANDAY(opened_at), take "
                "the day with DATE(opened_at) or the month with STRFTIME('%Y-%m', opened_at); "
                "all three accept both formats. REPLACE(REPLACE(opened_at, 'T', ' '), 'Z', '') "
                "gives the second format.",
            ),
            ColumnSpec(
                "resolved_at",
                "TEXT",
                "When the ticket was solved.",
                "Same formats as opened_at; NULL while open or pending. Hours to resolve: "
                "(JULIANDAY(resolved_at) - JULIANDAY(opened_at)) * 24.",
                nullable=True,
            ),
            ColumnSpec(
                "satisfaction_score",
                "INTEGER",
                "Customer rating after resolution, 1-5.",
                "NULL if the customer did not answer the survey.",
                nullable=True,
            ),
        ),
    ),
    TableSpec(
        "activities",
        "owner",
        "Logged sales and success activities: calls, emails, meetings, demos and notes.",
        (
            _pk("activity_id", "Activity identifier."),
            _tenant(),
            _owner("User who logged the activity (users.user_id)."),
            ColumnSpec(
                "account_id",
                "INTEGER",
                "Account the activity concerns.",
                references=("accounts", "account_id"),
            ),
            ColumnSpec(
                "contact_id",
                "INTEGER",
                "Contact involved.",
                "NULL for internal notes.",
                nullable=True,
                references=("contacts", "contact_id"),
            ),
            ColumnSpec(
                "deal_id",
                "INTEGER",
                "Deal the activity was logged against.",
                "NULL if not tied to a deal.",
                nullable=True,
                references=("deals", "deal_id"),
            ),
            ColumnSpec(
                "activity_type",
                "TEXT",
                "Kind of activity.",
                "One of 'call', 'email', 'meeting', 'demo', 'note'.",
            ),
            ColumnSpec("subject", "TEXT", "Short summary."),
            ColumnSpec(
                "occurred_at",
                "TEXT",
                "When the activity happened.",
                "Text 'YYYY-MM-DD HH:MM:SS' (UTC).",
            ),
            ColumnSpec(
                "duration_minutes",
                "INTEGER",
                "Length of the call, meeting or demo.",
                "NULL for emails and notes.",
                nullable=True,
            ),
            ColumnSpec("notes", "TEXT", "Free-text notes.", "NULL if none.", nullable=True),
        ),
    ),
)

TABLE_SPECS: dict[str, TableSpec] = {t.name: t for t in TABLES}


def create_table_sql(spec: TableSpec) -> str:
    lines = []
    for col in spec.columns:
        parts = [col.name, col.type]
        if col.primary_key:
            parts.append("PRIMARY KEY")
        elif not col.nullable:
            parts.append("NOT NULL")
        if col.references is not None:
            parts.append(f"REFERENCES {col.references[0]}({col.references[1]})")
        lines.append("  " + " ".join(parts))
    return f"CREATE TABLE {spec.name} (\n" + ",\n".join(lines) + "\n)"


def load_saas_schema(db_path: Path = DEFAULT_DB_PATH) -> DatabaseSchema:
    """Introspect the generated database and attach the dictionary's descriptions.

    Raises ValueError if the file has a table or column the dictionary does not describe, which
    means the database was produced by a different generator version.
    """
    raw = introspect_sqlite(db_path, db_id=SAAS_DB_ID)
    tables: list[Table] = []
    for table in raw.tables:
        spec = TABLE_SPECS.get(table.name)
        if spec is None:
            raise ValueError(f"{db_path}: table {table.name!r} is not in the SaaS data dictionary")
        tables.append(
            replace(
                table,
                description=spec.description,
                columns=tuple(_describe(spec, c) for c in table.columns),
            )
        )
    return DatabaseSchema(db_id=raw.db_id, tables=tuple(tables), foreign_keys=raw.foreign_keys)


def _describe(spec: TableSpec, column: Column) -> Column:
    col = spec.column(column.name)
    if col is None:
        raise ValueError(f"column {spec.name}.{column.name} is not in the SaaS data dictionary")
    return replace(column, description=col.description, value_description=col.value_description)
