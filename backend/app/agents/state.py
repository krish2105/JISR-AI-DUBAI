"""
state.py — The data that flows through one Jisr run (FROZEN CONTRACT, see docs/CONTRACTS.md).

Why this file exists:
    LangGraph passes one state object from agent to agent. Making it an explicit, typed
    Pydantic model means every agent knows exactly what it can read and write, and the
    whole state can be saved to the database so a run can pause for human approval.

Changing a field here affects the API, the dashboard and the replay files, so record
any change in docs/DECISIONS.md.
"""

from typing import Literal

from pydantic import BaseModel, Field

# The agents (graph nodes) in the order a normal run visits them.
# The dashboard and the 3D agent graph use these exact names.
AGENTS: tuple[str, ...] = (
    "ingest",       # parse the message, mask personal data
    "guard",        # injection / fraud screening of the untrusted message
    "supervisor",   # plans which workers run
    "quote",        # prices the items in INR and AED
    "duty",         # CEPA duty analysis (cited, indicative)
    "docs",         # document pack + consistency checker
    "trust",        # buyer trust signals (never verdicts)
    "outreach",     # bilingual reply drafts
    "governance",   # deterministic policy engine: approve / hold / block
)

RunStatus = Literal["new", "planning", "needs_approval", "approved", "sent", "blocked", "done"]


class LineItem(BaseModel):
    """One product line the buyer asked about."""

    description: str
    quantity: float
    unit: str = "pcs"
    target_price: float | None = None


class RFQ(BaseModel):
    """Structured enquiry extracted from the buyer's text (request for quotation)."""

    buyer_name: str
    buyer_country: str
    items: list[LineItem]
    incoterm: str | None = None
    deadline: str | None = None
    language: Literal["en", "ar", "mixed"] = "en"
    channel: Literal["whatsapp", "email", "form"] = "form"


class PendingAction(BaseModel):
    """Something an agent wants to do in the outside world. Only governance can let it out."""

    action_type: str                      # e.g. "send_message", "update_bank_details"
    title: str                            # short human-readable label for the inbox
    payload: dict = Field(default_factory=dict)
    requested_by: str                     # agent name
    reason: str = ""                      # why the agent wants this
    evidence: list[str] = Field(default_factory=list)


class RunState(BaseModel):
    """Everything a run needs; persisted so it can pause for approval and resume."""

    run_id: str
    org_id: str                                         # per-organisation isolation
    raw_message_redacted: str                           # models only ever see redacted text
    channel: Literal["whatsapp", "email", "form"] = "form"
    contact_key: str | None = None                      # hashed sender id (Phase 8); never a phone number
    memory: dict | None = None                          # buyer memory recalled at ingest (Phase 9b)
    injection_flags: list[str] = Field(default_factory=list)
    rfq: RFQ | None = None
    plan: list[str] = Field(default_factory=list)
    quote: dict | None = None                           # INR + AED, margin, FX source/time
    duty: dict | None = None                            # CEPA analysis, savings, evidence list
    docs: dict | None = None                            # generated document pack
    doc_issues: list[dict] = Field(default_factory=list)
    buyer_signals: list[dict] = Field(default_factory=list)
    drafts: list[dict] = Field(default_factory=list)
    pending_actions: list[PendingAction] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)
    impact: dict = Field(default_factory=dict)          # minutes saved, AED saved, risks caught
    status: RunStatus = "new"
