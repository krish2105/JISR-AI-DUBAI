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
        """On load: always UTC. Postgres returns the server's zone (not always UTC), SQLite drops it."""
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


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
    created_by: Mapped[str | None] = mapped_column(String(40), nullable=True)    # user id (four-eyes, Phase 13)


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
    # Per-organisation autonomy overrides {action_type: level}; only STRICTER than autonomy.yaml (Phase 15).
    autonomy: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class OrgProfile(Base):
    """An organisation's business profile (catalogue, costs, pricing policy, logistics) and onboarding progress.

    Organisations without a row (the demo organisation and demo sandboxes) use the synthetic demo profile.
    """

    __tablename__ = "org_profiles"

    org_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)                          # a validated BusinessProfile
    onboarding_step: Mapped[int] = mapped_column(Integer, default=0)
    onboarding_done: Mapped[bool] = mapped_column(default=False)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Contact(Base):
    """A buyer reachable on a channel. The phone number is needed to reply, so it is stored, but never shown to a
    model (runs only reference `contact_key`, a salted hash)."""

    __tablename__ = "contacts"

    contact_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(40), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    address: Mapped[str] = mapped_column(String(255))                # WhatsApp id, or A2A "task|context" ids
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
    number: Mapped[str | None] = mapped_column(String(40), nullable=True)   # shown to people (id is unique per org)
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


# --- Identity and access (Phase 13) -------------------------------------------------------------------------------


class User(Base):
    """A person who signs in. Passwords are stored only as salted scrypt hashes."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)     # lower-cased
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)  # None for demo visitors
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    session_version: Mapped[int] = mapped_column(Integer, default=1)    # bumped by "sign out everywhere"
    is_demo: Mapped[bool] = mapped_column(default=False)


class Organisation(Base):
    """An exporter's workspace. Every business row carries its `org_id`."""

    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    is_sandbox: Mapped[bool] = mapped_column(default=False)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)   # sandboxes only
    plan: Mapped[str | None] = mapped_column(String(30), nullable=True)                # billing plan key (Phase 19)


class Membership(Base):
    """A user's role in one organisation (a user may belong to several, with different roles)."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))            # owner|admin|approver|operator|accountant|auditor|viewer
    status: Mapped[str] = mapped_column(String(20), default="active")   # active|removed
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Invitation(Base):
    """An invitation link for a new team member. Only the SHA-256 of the token is stored."""

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ApiKey(Base):
    """A machine credential (MCP client) scoped to one organisation. Shown once; only its SHA-256 is stored."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10))            # mcp (A2A stays open to buyers' agents, DECISIONS S9)
    prefix: Mapped[str] = mapped_column(String(16))          # first characters, to recognise a key in the list
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class RateCounter(Base):
    """Fixed-window request counters shared by every API machine (rate limits, Phase 20). Old windows are pruned."""

    __tablename__ = "rate_counters"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)     # bucket:subject:window
    window_start: Mapped[int] = mapped_column(Integer, index=True)       # epoch seconds
    count: Mapped[int] = mapped_column(Integer, default=0)
