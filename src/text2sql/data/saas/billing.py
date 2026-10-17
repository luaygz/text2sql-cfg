"""Invoices, invoice lines and payments for one tenant."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from text2sql.data.saas.profile import AS_OF, LEGACY_BILLING_CUTOVER
from text2sql.data.saas.reference import DOMESTIC_TAX_RATE, USD_RATE, Plan
from text2sql.data.saas.world import Account, Record, World, add_months, on_day, ts

PAYMENT_METHODS: dict[str, tuple[tuple[str, float], ...]] = {
    "USD": (("card", 0.55), ("ach", 0.3), ("wire", 0.1), ("check", 0.05)),
    "EUR": (("card", 0.5), ("sepa_debit", 0.35), ("wire", 0.15)),
    "GBP": (("card", 0.55), ("bacs", 0.3), ("wire", 0.15)),
}
OTHER_PAYMENT_METHODS = (("card", 0.7), ("wire", 0.3))
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def due_text(issued: date, due: date) -> str:
    """Legacy-system invoices keep their US-format due dates; newer ones are ISO."""
    return due.strftime("%m/%d/%Y") if issued < LEGACY_BILLING_CUTOVER else due.isoformat()


class Biller:
    def __init__(self, world: World, tenant: Record, home_country: str) -> None:
        self.w = world
        self.tenant = tenant
        self.home_country = home_country
        self.invoices: list[Record] = []

    def bill(
        self, acct: Account, sub: Record, plan: Plan, *, discount: float, start: date, end: date
    ) -> bool:
        """Invoice every period from `start` until `end`; True if one is overdue and unpaid."""
        unit = round(plan.price_per_seat / USD_RATE[acct.currency], 2)
        overdue = False
        k = 0
        while (issued := add_months(start, k * plan.months)) < end:
            period = f"{MONTHS[issued.month - 1]} {issued.year}"
            if plan.months == 12:
                last = add_months(issued, 11)
                period += f" - {MONTHS[last.month - 1]} {last.year}"
            lines = [(f"{plan.name}, {period}", acct.seats, unit)]
            if discount:
                gross = round(acct.seats * unit, 2)
                lines.append((f"Discount {discount:g}%", 1, -round(gross * discount / 100, 2)))
            invoice, due = self.invoice(acct, sub, issued, lines)
            overdue = overdue or (invoice.values["status"] == "open" and due < AS_OF)
            k += 1
        return overdue

    def invoice(
        self,
        acct: Account,
        sub: Record | None,
        issued: date,
        lines: Sequence[tuple[str, int, float]],
    ) -> tuple[Record, date]:
        """Issue an invoice with its lines, collect it, and return it with its due date."""
        w = self.w
        totals = [round(quantity * unit, 2) for _, quantity, unit in lines]
        subtotal = round(sum(totals), 2)
        rate = DOMESTIC_TAX_RATE.get(self.home_country, 0.0)
        tax = round(subtotal * rate, 2) if acct.country == self.home_country else 0.0
        total = round(subtotal + tax, 2)
        due = issued + timedelta(days=acct.terms)
        created = on_day(issued, 6)
        invoice = w.add(
            "invoices",
            created,
            tenant_id=self.tenant,
            owner_user_id=acct.owner,
            account_id=acct.record,
            subscription_id=sub,
            invoice_number="",
            status="open",
            currency_code=acct.currency,
            issued_at=issued.isoformat(),
            due_date=due_text(issued, due),
            subtotal=subtotal,
            tax=tax,
            total_amount=total,
        )
        for (text, quantity, unit), line_total in zip(lines, totals, strict=True):
            w.add(
                "invoice_line_items",
                created,
                tenant_id=self.tenant,
                owner_user_id=acct.owner,
                invoice_id=invoice,
                description=text,
                quantity=quantity,
                unit_price=unit,
                line_total=line_total,
            )
        self.invoices.append(invoice)
        invoice.values["status"] = self._collect(acct, invoice, issued, due, total)
        return invoice, due

    def number_invoices(self) -> None:
        """Number invoices per calendar year in issue order, once all of them exist."""
        counters: dict[str, int] = {}
        for invoice in sorted(self.invoices, key=lambda r: str(r.values["issued_at"])):
            year = str(invoice.values["issued_at"])[:4]
            counters[year] = counters.get(year, 0) + 1
            invoice.values["invoice_number"] = f"INV-{year}-{counters[year]:05d}"

    def _collect(
        self, acct: Account, invoice: Record, issued: date, due: date, total: float
    ) -> str:
        """Record payment attempts for an invoice and return its resulting status."""
        w = self.w
        if w.chance(0.01):
            return "void"
        if due < AS_OF and w.chance(0.03):
            return "uncollectible" if (AS_OF - due).days > 90 else "open"
        paid_on = issued + timedelta(days=w.rng.randint(0, acct.terms + 12))
        if paid_on >= AS_OF:
            return "open"
        paid_at = w.between(on_day(paid_on), on_day(paid_on) + timedelta(days=1))
        earliest = on_day(issued, 7)
        cents = round(total * 100)
        method = w.weighted(PAYMENT_METHODS.get(acct.currency, OTHER_PAYMENT_METHODS))
        if w.chance(0.04):
            retry_gap = timedelta(days=w.rng.randint(1, 4))
            self._payment(
                acct,
                invoice,
                max(paid_at - retry_gap, earliest),
                cents,
                method=method,
                status="failed",
            )
        pending = (AS_OF - paid_on).days <= 3
        if not pending and w.chance(0.03):  # paid in two instalments
            first = round(cents * w.rng.uniform(0.3, 0.7))
            first_at = max(paid_at - timedelta(days=w.rng.randint(5, 10)), earliest)
            self._payment(acct, invoice, first_at, first, method=method, status="succeeded")
            self._payment(acct, invoice, paid_at, cents - first, method=method, status="succeeded")
        else:
            self._payment(
                acct,
                invoice,
                paid_at,
                cents,
                method=method,
                status="pending" if pending else "succeeded",
            )
        return "open" if pending else "paid"

    def _payment(
        self, acct: Account, invoice: Record, at: datetime, cents: int, *, method: str, status: str
    ) -> None:
        self.w.add(
            "payments",
            at,
            tenant_id=self.tenant,
            owner_user_id=acct.owner,
            invoice_id=invoice,
            amount=cents,
            currency_code=acct.currency,
            method=method,
            status=status,
            paid_at=ts(at),
            processor_ref=f"pay_{self.w.hex(64)}",
        )
