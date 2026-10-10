"""
models.py — Database tables (SQLAlchemy 2 ORM).

Why this file exists:
    Runs, their events, approval requests and the audit log must survive restarts and be
    queryable by the dashboard. Each class below is one table. Every table carries `org_id`
    so one organisation can never read another's data (per-organisation isolation).

Tables (Phase 1):
    runs        one row per enquiry processed; holds the latest RunState as JSON
    run_events  the ordered event stream of each run (drives timeline, graph, replay)
    approvals   actions waiting for (or decided by) a human
    audit_log   append-only, hash-chained record of who/what did what (see governance/audit.py)
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    """Current time in UTC (always store UTC; convert to local time only for display)."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """A timestamp column that always comes back timezone-aware in UTC.

    Why: SQLite stores datetimes without a timezone, so they come back "naive". A browser
    then reads them as LOCAL time (e.g. India +5:30) and every duration is off by hours.
    Postgres keeps the zone; this type makes both databases behave the same.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        """On save: store everything as UTC."""
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        """On load: attach UTC if the database dropped the zone."""
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    """Parent class of every table."""


class Run(Base):
    """One processed enquiry."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="new")
    channel: Mapped[str] = mapped_column(String(20), default="form")
    sample_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    raw_redacted: Mapped[str] = mapped_column(Text)        # never the unredacted message
    contact_key: Mapped[str | None] = mapped_column(String(64), nullable=True)   # who to reply to (Phase 8)
    state: Mapped[dict] = mapped_column(JSON, default=dict)  # latest RunState as JSON


class RunEventRow(Base):
    """One stored RunEvent."""

    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_run_event_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    agent: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    risk: Mapped[str | None] = mapped_column(String(10), nullable=True)


class Approval(Base):
    """An action held for a human decision."""

    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    org_id: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    action_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)     # e.g. the draft message
    reason: Mapped[str] = mapped_column(Text, default="")         # why the agent wants it
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    risk: Mapped[str] = mapped_column(String(10), default="medium")
    rule_id: Mapped[str] = mapped_column(String(40))              # policy rule that required approval
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    decided_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEntry(Base):
    """One append-only audit record, chained to the previous one by hash."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(40), index=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    actor: Mapped[str] = mapped_column(String(80))       # agent name, "human:<who>" or "system"
    action: Mapped[str] = mapped_column(String(60))      # e.g. "approval.approved", "policy.blocked"
    run_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class OrgSettings(Base):
    """Per-organisation governance switches (one row per organisation)."""

    __tablename__ = "org_settings"

    org_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kill_switch: Mapped[bool] = mapped_column(default=False)          # True = nothing leaves Jisr
    kill_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Contact(Base):
    """A buyer reachable on a channel. The phone number is needed to reply, so it is stored, but never shown to a
    model (runs only reference `contact_key`, a salted hash)."""

    __tablename__ = "contacts"

    contact_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(40), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    address: Mapped[str] = mapped_column(String(64))                 # WhatsApp id (phone number)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)   # 24 h window


class InboundLog(Base):
    """Inbound message ids already handled (webhooks can be delivered more than once)."""

    __tablename__ = "inbound_log"

    message_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(40), index=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))


class Invoice(Base):
    """An issued export invoice (collections). Demo data is synthetic and seeded for the demo org only."""

    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(40), index=True)
    buyer_name: Mapped[str] = mapped_column(String(160))
    contact_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="en")
    amount_aed: Mapped[float] = mapped_column()
    issued_on: Mapped[datetime] = mapped_column(UTCDateTime())
    due_on: Mapped[datetime] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(20), default="open")          # open | paid (paid only by a human)
    last_reminder_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class BuyerMemory(Base):
    """What Jisr remembers about a buyer across runs (per organisation, keyed by the hashed contact).

    Facts only (counts, last Incoterm, languages, last quote total, past high-risk signals): no message text and no
    personal data, so it can be shown to the owner and used by agents safely.
    """

    __tablename__ = "buyer_memory"

    contact_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    runs: Mapped[int] = mapped_column(default=0)
    quotes_sent: Mapped[int] = mapped_column(default=0)                 # approved and delivered
    last_incoterm: Mapped[str | None] = mapped_column(String(10), nullable=True)
    last_quote_total_aed: Mapped[float | None] = mapped_column(nullable=True)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    risk_signals: Mapped[list] = mapped_column(JSON, default=list)      # high-risk signal names ever raised
