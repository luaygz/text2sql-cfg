"""Synthesise the SaaS CRM world in memory, deterministically from one seed.

All randomness flows through one `World` (a seeded `random.Random` plus a seeded Faker), called
in a fixed order; nothing reads the clock, iterates a set, or depends on string hashing. Integer
ids are assigned at the end in creation-time order, so ids interleave tenants the way they would
in a real shared database.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import date, datetime, timedelta

from text2sql.data.saas.billing import Biller, due_text
from text2sql.data.saas.planted import PlantedInjection, canary_token, planted_injections
from text2sql.data.saas.profile import (
    ACTIVITY_SUBJECTS,
    AS_OF,
    COMPANY_SUFFIXES,
    GENERATED_NAME_POOL,
    JOB_TITLES,
    LEAD_SOURCES,
    SAAS_SEED,
    SALES_TEAM_NAMES,
    SERVICES,
    SHARED_ACCOUNT_NAMES,
    SHARED_NAME_PROBABILITY,
    TENANTS,
    TICKET_SUBJECTS,
    TenantProfile,
)
from text2sql.data.saas.reference import (
    COUNTRY_CURRENCY,
    COUNTRY_REGION,
    INDUSTRIES,
    PLANS,
    USD_RATE,
    Plan,
)
from text2sql.data.saas.world import (
    AS_OF_START,
    Account,
    Record,
    World,
    add_months,
    on_day,
    ts,
    ts_z,
)

LEGACY_PLAN_UNTIL = date(2024, 1, 1)
PLAN_BY_TIER = {(p.tier, p.billing_period): p for p in PLANS if p.is_active}
LEGACY_PLAN = next(p for p in PLANS if not p.is_active)

OPEN_STAGES = (
    ("prospecting", 0.3),
    ("qualification", 0.3),
    ("proposal", 0.25),
    ("negotiation", 0.15),
)
STAGE_PROBABILITY = {
    "prospecting": 10,
    "qualification": 25,
    "proposal": 50,
    "negotiation": 75,
    "closed_won": 100,
    "closed_lost": 0,
}
DISCOUNTS = ((0.0, 0.7), (10.0, 0.15), (15.0, 0.08), (20.0, 0.05), (30.0, 0.02))
PAYMENT_TERMS = ((30, 0.7), (15, 0.15), (45, 0.15))
PRIORITIES = (("Low", 0.25), ("Normal", 0.45), ("High", 0.22), ("Urgent", 0.08))
CHANNELS = (("email", 0.4), ("web", 0.25), ("chat", 0.2), ("phone", 0.1), ("api", 0.05))
ACTIVITY_TYPES = (("email", 0.35), ("call", 0.3), ("meeting", 0.18), ("demo", 0.07), ("note", 0.1))
ACTIVITY_MINUTES = {"call": (5, 45), "meeting": (30, 90), "demo": (30, 60)}
SCORES = ((5, 0.45), (4, 0.3), (3, 0.12), (2, 0.07), (1, 0.06))


def build_records(seed: int = SAAS_SEED) -> dict[str, list[Record]]:
    """Every non-reference table's rows, keyed by table name and sorted by id."""
    world = World(seed)
    pool = _name_pool(world)
    for profile in TENANTS:
        shared = [n for n in SHARED_ACCOUNT_NAMES if world.chance(SHARED_NAME_PROBABILITY)]
        names = shared + world.rng.sample(pool, profile.accounts - len(shared))
        world.rng.shuffle(names)
        _TenantBuilder(world, profile).build(names)
    for table, records in world.tables.items():
        if table != "tenants":  # tenant ids are fixed by the profiles
            order = sorted(range(len(records)), key=lambda i: (records[i].created, i))
            for new_id, i in enumerate(order, start=1):
                records[i].id = new_id
        records.sort(key=lambda r: r.id)
    return world.tables


def _name_pool(world: World) -> list[str]:
    seen = {n.lower() for n in SHARED_ACCOUNT_NAMES}
    names: list[str] = []
    while len(names) < GENERATED_NAME_POOL:
        if world.chance(0.7):
            name = f"{world.fake.last_name()} {world.rng.choice(COMPANY_SUFFIXES)}"
        else:
            name = str(world.fake.company())
        if name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names


def _domain(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum()) + ".example"


class _TenantBuilder:
    def __init__(self, world: World, profile: TenantProfile) -> None:
        self.w = world
        self.p = profile
        self.signup = on_day(profile.signed_up, 10)
        self.tenant = world.add(
            "tenants",
            self.signup,
            name=profile.name,
            country_code=profile.country_code,
            default_currency_code=profile.currency_code,
            signed_up_at=ts(self.signup),
            api_key=f"t2s_test_{world.hex(128)}",
        )
        self.tenant.id = profile.tenant_id
        self.emails: set[str] = set()
        self.sales: list[Record] = []
        self.sales_weights: list[float] = []
        self.support: list[Record] = []
        self.success: list[Record] = []
        self.accounts: list[Record] = []
        self.customers: list[Account] = []
        """Accounts with a live subscription; planted rows attach to one of them."""
        self.billing = Biller(world, self.tenant, profile.country_code)

    def build(self, account_names: Sequence[str]) -> None:
        admin = self._staff()
        self._canaries(admin)
        for name in account_names:
            self._organic_account(name)
        for injection in planted_injections():
            if injection.tenant_id == self.p.tenant_id:
                self._plant(injection)
        self.billing.number_invoices()

    # People

    def _staff(self) -> Record:
        accounts = self.p.accounts
        admin = self._user("admin", None, None)
        teams = [
            self._team(n, "sales")
            for n in SALES_TEAM_NAMES[: 1 + int(accounts >= 100) + int(accounts >= 180)]
        ]
        managers = [self._user("manager", team, admin) for team in teams]
        for i in range(max(3, accounts // 14)):
            self.sales.append(
                self._user("sales_rep", teams[i % len(teams)], managers[i % len(managers)])
            )
        self.sales_weights = [self.w.rng.paretovariate(1.5) for _ in self.sales]
        support = self._team("Support", "support")
        lead = self._user("manager", support, admin)
        self.support = [
            self._user("support_agent", support, lead) for _ in range(max(2, accounts // 30))
        ]
        success = self._team("Customer Success", "success")
        self.success = [self._user("csm", success, admin) for _ in range(max(1, accounts // 45))]
        return admin

    def _team(self, name: str, department: str) -> Record:
        return self.w.add(
            "teams", self.signup, tenant_id=self.tenant, name=name, department=department
        )

    def _user(self, role: str, team: Record | None, manager: Record | None) -> Record:
        w = self.w
        first, last = w.name()
        if role in ("admin", "manager") or w.chance(0.6):
            created = self.signup + timedelta(hours=w.rng.randint(1, 72))
        else:
            created = w.between(self.signup + timedelta(days=30), AS_OF_START - timedelta(days=14))
        active = role == "admin" or not w.chance(0.08)
        if not active:
            last_login: datetime | None = w.between(created, AS_OF_START - timedelta(days=30))
        elif w.chance(0.03):
            last_login = None
        else:
            last_login = w.between(max(created, AS_OF_START - timedelta(days=21)), AS_OF_START)
        local = "".join(ch for ch in f"{first}.{last}".lower() if ch.isalnum() or ch == ".")
        email, n = f"{local}@{self.p.domain}", 2
        while email in self.emails:
            email, n = f"{local}{n}@{self.p.domain}", n + 1
        self.emails.add(email)
        return w.add(
            "users",
            created,
            tenant_id=self.tenant,
            team_id=team,
            manager_user_id=manager,
            full_name=f"{first} {last}",
            email=email,
            role=role,
            is_active=int(active),
            created_at=ts(created),
            last_login_at=None if last_login is None else ts(last_login),
            password_hash=self._password_hash(email),
        )

    def _password_hash(self, email: str) -> str:
        """Fake but realistically shaped hash; no password exists behind it."""
        salt = self.w.hex(48)
        digest = hashlib.sha256(f"{salt}:{email}".encode()).hexdigest()
        return f"pbkdf2_sha256$600000${salt}${digest}"

    def _sales_owner(self) -> Record:
        return self.w.rng.choices(self.sales, weights=self.sales_weights)[0]

    # Accounts and the sales funnel

    def _account_record(self, name: str, clean_name: str, created: datetime) -> Account:
        w = self.w
        country = self._country()
        currency = self.p.currency_code
        if country is not None and w.chance(0.25):
            currency = COUNTRY_CURRENCY[country]
        employees = max(2, int(w.rng.lognormvariate(4.0, 1.2)))
        seats = min(600, max(2, round(employees * w.rng.uniform(0.15, 0.6))))
        owner = self._sales_owner()
        terms = w.weighted(PAYMENT_TERMS)
        parent = w.rng.choice(self.accounts) if self.accounts and w.chance(0.05) else None
        record = w.add(
            "accounts",
            created,
            tenant_id=self.tenant,
            owner_user_id=owner,
            parent_account_id=parent,
            name=name,
            industry_id=None if w.chance(0.08) else w.rng.randint(1, len(INDUSTRIES)),
            country_code=country,
            currency_code=currency,
            lifecycle_stage="prospect",
            employee_count=None if w.chance(0.15) else employees,
            website=None if w.chance(0.2) else _domain(clean_name),
            payment_terms_days=terms,
            created_at=ts(created),
        )
        self.accounts.append(record)
        return Account(record, clean_name, created, owner, currency, country, seats, terms)

    def _country(self) -> str | None:
        w, home = self.w, self.p.country_code
        if w.chance(0.03):
            return None
        if w.chance(0.6):
            return home
        neighbours = [
            c
            for c, region in COUNTRY_REGION.items()
            if region == COUNTRY_REGION[home] and c != home
        ]
        if neighbours and w.chance(0.75):
            return w.rng.choice(neighbours)
        return w.rng.choice(list(COUNTRY_REGION))

    def _organic_account(self, name: str) -> None:
        w = self.w
        if w.chance(0.3):  # bulk import when the tenant signed up
            created = self.signup + timedelta(hours=w.rng.randint(2, 48))
        else:
            created = w.between(self.signup, AS_OF_START - timedelta(days=1))
        acct = self._account_record(w.vary_case(name, 0.03, 0.04), name, created)
        for i in range(1 + min(7, w.geometric(0.45))):
            when = w.between(created, min(created + timedelta(days=30), AS_OF_START))
            acct.contacts.append(self._contact(acct, when, primary=i == 0))
        r = w.rng.random()
        if r < 0.03:
            acct.lifecycle = "partner"
        elif r < 0.35:
            self._prospect_deals(acct)
        else:
            self._customer(acct)
        acct.record.values["lifecycle_stage"] = w.vary_case(acct.lifecycle.title(), 0.35, 0.1)
        self._activities(acct)

    def _contact(self, acct: Account, created: datetime, *, primary: bool) -> Record:
        w = self.w
        first, last = w.name()
        email = None
        if not w.chance(0.08):
            local = "".join(ch for ch in f"{first}.{last}" if ch.isalnum() or ch == ".")
            email = w.vary_case(f"{local}@{_domain(acct.name)}", 0.85, 0.05)
        title = None
        if not w.chance(0.15):
            title = w.vary_case(w.rng.choice(JOB_TITLES), 0.05, 0.03)
            if w.chance(0.04):
                title += " "
        return w.add(
            "contacts",
            created,
            tenant_id=self.tenant,
            owner_user_id=acct.owner if w.chance(0.85) else self._sales_owner(),
            account_id=acct.record,
            first_name=first,
            last_name=last,
            email=email,
            phone=None if w.chance(0.35) else str(w.fake.phone_number()),
            job_title=title,
            is_primary=int(primary),
            created_at=ts(created),
        )

    def _plan(self, seats: int, start: date) -> Plan:
        w = self.w
        tier = (
            "starter"
            if seats <= 10
            else "growth"
            if seats <= 50
            else "business"
            if seats <= 250
            else "enterprise"
        )
        if tier == "growth" and seats <= 25 and start < LEGACY_PLAN_UNTIL and w.chance(0.3):
            return LEGACY_PLAN
        annual = tier == "enterprise" or w.chance(self.p.annual_share)
        return PLAN_BY_TIER[tier, "annual" if annual else "monthly"]

    def _deal(
        self,
        acct: Account,
        opened: datetime,
        stage: str,
        closed: datetime | None,
        *,
        seats: int,
        plan: Plan,
        discount: float,
        name: str,
    ) -> Record:
        w = self.w
        yearly_usd = seats * plan.price_per_seat * (12 // plan.months) * (1 - discount / 100)
        if closed is not None:
            expected = closed.date() + timedelta(days=w.rng.randint(-20, 25))
        elif w.chance(0.15):  # stale forecast the rep never updated
            expected = opened.date() + timedelta(days=w.rng.randint(30, 90))
        else:
            expected = AS_OF + timedelta(days=w.rng.randint(5, 120))
        record = w.add(
            "deals",
            opened,
            tenant_id=self.tenant,
            owner_user_id=acct.owner if w.chance(0.9) else self._sales_owner(),
            account_id=acct.record,
            name=name,
            stage=stage,
            amount=float(round(yearly_usd / USD_RATE[acct.currency], -1)),
            currency_code=acct.currency,
            probability=None if w.chance(0.12) else STAGE_PROBABILITY[stage],
            lead_source=None if w.chance(0.15) else w.rng.choice(LEAD_SOURCES),
            expected_close_date=expected.isoformat(),
            created_at=ts(opened),
            closed_at=None if closed is None else ts(closed),
        )
        acct.deals.append((record, opened, closed))
        return record

    def _pipeline_deal(
        self, acct: Account, opened: datetime, label: str, *, may_stay_open: bool = True
    ) -> None:
        """An open or lost deal: recent ones are still open, old ones mostly lost."""
        w = self.w
        seats = max(2, round(acct.seats * w.rng.uniform(0.2, 1.0)))
        plan = self._plan(seats, opened.date())
        recent = (AS_OF_START - opened).days < 150
        if may_stay_open and (recent or w.chance(0.25)):
            stage, closed = w.weighted(OPEN_STAGES), None
        else:
            stage = "closed_lost"
            closed = min(
                opened + timedelta(days=w.rng.uniform(14, 120)), AS_OF_START - timedelta(hours=1)
            )
        self._deal(
            acct,
            opened,
            stage,
            closed,
            seats=seats,
            plan=plan,
            discount=0.0,
            name=f"{acct.name} - {label}",
        )

    def _prospect_deals(self, acct: Account) -> None:
        for _ in range(self.w.weighted(((0, 0.3), (1, 0.5), (2, 0.2)))):
            self._pipeline_deal(acct, self.w.between(acct.created, AS_OF_START), "New business")

    def _customer(self, acct: Account) -> None:
        w = self.w
        self_serve = w.chance(0.2)
        if self_serve:
            deal_opened = None
            start_dt = acct.created + timedelta(days=w.rng.uniform(0, 10))
        else:
            deal_opened = acct.created + timedelta(days=w.rng.uniform(0, 30))
            start_dt = deal_opened + timedelta(days=w.rng.uniform(14, 120))
        start = start_dt.date()
        if start.day > 28:  # billing anchors stay on days every month has
            start = add_months(start.replace(day=1), 1)
        if start >= AS_OF:
            if deal_opened is not None and deal_opened < AS_OF_START:
                self._pipeline_deal(acct, deal_opened, "New business")
            return
        plan = self._plan(acct.seats, start)
        discount = w.weighted(DISCOUNTS)
        deal = None
        if deal_opened is not None:
            deal = self._deal(
                acct,
                deal_opened,
                "closed_won",
                start_dt,
                seats=acct.seats,
                plan=plan,
                discount=discount,
                name=f"{acct.name} - {plan.tier.title()} ({acct.seats} seats)",
            )
        canceled = self._subscribe(
            acct,
            plan,
            deal,
            discount=discount,
            started=start_dt,
            start=start,
            self_serve=self_serve,
        )
        end = canceled or AS_OF
        acct.lifecycle = "churned" if canceled else "customer"
        if canceled:
            acct.active_until = min(on_day(canceled) + timedelta(days=60), AS_OF_START)
        else:
            self.customers.append(acct)
        for _ in range(w.weighted(((0, 0.6), (1, 0.3), (2, 0.1)))):
            opened = w.between(start_dt, on_day(end))
            self._pipeline_deal(
                acct, opened, w.rng.choice(("Expansion", "Upgrade")), may_stay_open=canceled is None
            )
        self._tickets(acct, start, end)

    def _subscribe(
        self,
        acct: Account,
        plan: Plan,
        deal: Record | None,
        *,
        discount: float,
        started: datetime,
        start: date,
        self_serve: bool,
    ) -> date | None:
        """Create the subscription and bill it; return the cancellation date, if any."""
        w = self.w
        canceled = None
        if (AS_OF - start).days > 150 and w.chance(0.18):
            canceled = start + timedelta(days=w.rng.randint(90, (AS_OF - start).days - 1))
        trialing = self_serve and (AS_OF - start).days < 14
        sub = w.add(
            "subscriptions",
            started,
            tenant_id=self.tenant,
            owner_user_id=acct.owner,
            account_id=acct.record,
            plan_id=plan.plan_id,
            deal_id=deal,
            status="active",
            seats=acct.seats,
            discount_pct=discount,
            currency_code=acct.currency,
            started_at=start.isoformat(),
            canceled_at=None if canceled is None else canceled.isoformat(),
        )
        end = canceled or AS_OF
        overdue = False
        if not trialing:
            overdue = self.billing.bill(acct, sub, plan, discount=discount, start=start, end=end)
            if w.chance(0.15):
                issued = start + timedelta(days=w.rng.randint(0, 20))
                service, usd = w.rng.choice(SERVICES)
                if issued < end:
                    self.billing.invoice(
                        acct, None, issued, [(service, 1, round(usd / USD_RATE[acct.currency], 2))]
                    )
        sub.values["status"] = (
            "canceled"
            if canceled
            else "trialing"
            if trialing
            else "past_due"
            if overdue
            else "active"
        )
        return canceled

    # Support and activity history

    def _tickets(self, acct: Account, start: date, end: date) -> None:
        w = self.w
        years = (end - start).days / 365
        for _ in range(min(15, w.poisson((1.5 + acct.seats / 80) * years))):
            self._ticket(acct, w.between(on_day(start), on_day(end)))

    def _ticket(self, acct: Account, opened: datetime) -> Record:
        w = self.w
        channel = w.weighted(CHANNELS)
        stamp = ts_z if channel in ("web", "api") else ts
        age_days = (AS_OF_START - opened).days
        if age_days < 3:
            status = w.rng.choice(("open", "pending"))
        elif age_days < 10:
            status = w.weighted((("open", 0.2), ("pending", 0.2), ("solved", 0.6)))
        else:
            status = w.weighted((("solved", 0.7), ("closed", 0.27), ("open", 0.03)))
        resolved = None
        if status in ("solved", "closed"):
            resolved = min(
                opened + timedelta(hours=w.rng.lognormvariate(2.5, 1.2)),
                AS_OF_START - timedelta(seconds=1),
            )
        rated = resolved is not None and w.chance(0.55)
        return w.add(
            "tickets",
            opened,
            tenant_id=self.tenant,
            owner_user_id=w.rng.choice(self.support if w.chance(0.9) else self.success),
            account_id=acct.record,
            contact_id=w.rng.choice(acct.contacts) if w.chance(0.9) else None,
            subject=w.rng.choice(TICKET_SUBJECTS).format(seats=w.rng.randint(2, 25)),
            description=w.sentence() if w.chance(0.85) else None,
            priority=w.vary_case(w.weighted(PRIORITIES), 0.6, 0.1),
            status=status,
            channel=channel,
            opened_at=stamp(opened),
            resolved_at=None if resolved is None else stamp(resolved),
            satisfaction_score=w.weighted(SCORES) if rated else None,
        )

    def _activities(self, acct: Account) -> None:
        w = self.w
        years = max(0.0, (acct.active_until - acct.created).days / 365)
        rate = 4.0 if acct.lifecycle in ("customer", "churned") else 1.5
        for _ in range(min(30, w.poisson(2 + rate * years))):
            self._activity(acct, w.between(acct.created, acct.active_until))

    def _activity(self, acct: Account, when: datetime) -> Record:
        w = self.w
        kind = w.weighted(ACTIVITY_TYPES)
        open_deals = [
            d
            for d, opened, closed in acct.deals
            if opened <= when and (closed is None or when <= closed)
        ]
        minutes = ACTIVITY_MINUTES.get(kind)
        return w.add(
            "activities",
            when,
            tenant_id=self.tenant,
            owner_user_id=acct.owner if w.chance(0.75) else w.rng.choice(self.sales + self.success),
            account_id=acct.record,
            contact_id=None if kind == "note" else w.rng.choice(acct.contacts),
            deal_id=w.rng.choice(open_deals) if open_deals and w.chance(0.6) else None,
            activity_type=kind,
            subject=w.rng.choice(ACTIVITY_SUBJECTS[kind]),
            occurred_at=ts(when),
            duration_minutes=None if minutes is None else w.rng.randint(*minutes),
            notes=w.sentence() if w.chance(0.4) else None,
        )

    # Planted rows

    def _canaries(self, admin: Record) -> None:
        w, token, currency = self.w, canary_token(self.p.tenant_id), self.p.currency_code
        at = self.signup + timedelta(minutes=30)
        day = at.date()
        email = f"{token.lower()}@canary.invalid"
        team = w.add("teams", at, tenant_id=self.tenant, name=token, department="sales")
        user = w.add(
            "users",
            at,
            tenant_id=self.tenant,
            team_id=team,
            manager_user_id=admin,
            full_name=token,
            email=email,
            role="sales_rep",
            is_active=0,
            created_at=ts(at),
            last_login_at=None,
            password_hash=self._password_hash(email),
        )
        owned = {"tenant_id": self.tenant, "owner_user_id": user}
        account = w.add(
            "accounts",
            at,
            **owned,
            parent_account_id=None,
            name=token,
            industry_id=None,
            country_code=None,
            currency_code=currency,
            lifecycle_stage="prospect",
            employee_count=None,
            website=None,
            payment_terms_days=30,
            created_at=ts(at),
        )
        contact = w.add(
            "contacts",
            at,
            **owned,
            account_id=account,
            first_name="Canary",
            last_name=token,
            email=email,
            phone=None,
            job_title=None,
            is_primary=1,
            created_at=ts(at),
        )
        deal = w.add(
            "deals",
            at,
            **owned,
            account_id=account,
            name=token,
            stage="closed_lost",
            amount=0.0,
            currency_code=currency,
            probability=0,
            lead_source=None,
            expected_close_date=day.isoformat(),
            created_at=ts(at),
            closed_at=ts(at + timedelta(hours=1)),
        )
        invoice = w.add(
            "invoices",
            at,
            **owned,
            account_id=account,
            subscription_id=None,
            invoice_number=token,
            status="void",
            currency_code=currency,
            issued_at=day.isoformat(),
            due_date=due_text(day, day + timedelta(days=30)),
            subtotal=0.0,
            tax=0.0,
            total_amount=0.0,
        )
        w.add(
            "invoice_line_items",
            at,
            **owned,
            invoice_id=invoice,
            description=token,
            quantity=1,
            unit_price=0.0,
            line_total=0.0,
        )
        w.add(
            "payments",
            at,
            **owned,
            invoice_id=invoice,
            amount=0,
            currency_code=currency,
            method="card",
            status="failed",
            paid_at=ts(at),
            processor_ref=token,
        )
        w.add(
            "tickets",
            at,
            **owned,
            account_id=account,
            contact_id=contact,
            subject=token,
            description=None,
            priority="low",
            status="closed",
            channel="email",
            opened_at=ts(at),
            resolved_at=ts(at + timedelta(hours=1)),
            satisfaction_score=None,
        )
        w.add(
            "activities",
            at,
            **owned,
            account_id=account,
            contact_id=None,
            deal_id=deal,
            activity_type="note",
            subject=token,
            occurred_at=ts(at),
            duration_minutes=None,
            notes=None,
        )

    def _plant(self, injection: PlantedInjection) -> None:
        """Store the injection where its innocent question finds it: the tenant's newest row."""
        at = AS_OF_START + timedelta(hours=10)
        host = self.w.rng.choice(self.customers)
        match injection.table, injection.column:
            case "accounts", "name":
                self._account_record(injection.text, injection.text, at)
            case "tickets", "subject":
                ticket = self._ticket(host, at)
                ticket.values.update(
                    subject=injection.text, priority="urgent", channel="web", opened_at=ts_z(at)
                )
            case "contacts", "job_title":
                self._contact(host, at, primary=False).values["job_title"] = injection.text
            case "activities", "notes":
                self._activity(host, at).values["notes"] = injection.text
            case "invoice_line_items", "description":
                self.billing.invoice(host, None, AS_OF, [(injection.text, 1, 950.0)])
            case "deals", "name":
                self._deal(
                    host,
                    at,
                    "proposal",
                    None,
                    seats=host.seats,
                    plan=self._plan(host.seats, AS_OF),
                    discount=0.0,
                    name=injection.text,
                )
            case _:
                raise ValueError(f"no placement for {injection.table}.{injection.column}")
