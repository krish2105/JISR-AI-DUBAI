"""
injection_guard.py — Screen untrusted inbound messages for injection and fraud (v1, rule layer).

Why this file exists:
    Every buyer message is UNTRUSTED DATA. Before agents plan anything, the guard looks for attempts to
    override instructions, extract prompts or secrets, change bank details, rush or fake payments, skip
    human approval, or smuggle instructions inside attachments, file names and metadata. It returns flag
    codes plus the evidence (matched text) so a human can see WHY a message was flagged. It never edits
    or executes the message.

    Two layers (see classifier.py for the second):
      1. Rules (this file): deterministic, bilingual, run on several normalised "views" of the text so
         obfuscation ("i g n o r e", "upd8 b@nk", zero-width characters, Arabic letter variants) is undone.
      2. An LLM classifier on the `fast` role (Phase 3) whose findings are ADDED to the rule flags.
    Flags raise the risk; the deterministic policy engine still decides what may happen (defence in depth).

Design discipline: the rules were developed on eval/synth/adversarial_dev.py (dev split) and its benign
lookalikes. The 30 cases in eval/synth/adversarial.py are the held-out test set and were not used for tuning.
"""

import re

from pydantic import BaseModel, Field

from app.security.normalize import normalize_arabic, views

FLAGS = ("instruction_override", "prompt_exfiltration", "bank_change", "payment_pressure", "payment_status",
         "approval_bypass", "hidden_instruction")


def _rx(pattern: str) -> re.Pattern:
    """Compile a pattern after applying the SAME Arabic normalisation as the text views."""
    return re.compile(normalize_arabic(pattern), re.IGNORECASE | re.DOTALL)


# ---- building blocks (English) -------------------------------------------------------------
_EN_BANKISH = (r"(banks?\b|bank(ing)? (details|account|info\w*)|iban|beneficiary|remittance( account| details)?|"
               r"account (number|no\.?|details|no\b)|a/c( no\.?)?|acct\b|swift|routing number|\[iban_\d+\])")
_EN_CHANGE = (r"(chang\w*|chnge|updat\w*|amend\w*|switch\w*|replac\w*|modif\w*|new\b|closed|"
              r"(is|are) now|has been changed|have changed)")
_EN_PAY = r"(pay\w*|transfer\w*|wire\w*|remit\w*|deposit|money|funds|balance|send the amount)"
_EN_URGENT = (r"(urgent\w*|immediately|right now|\bnow\b|today|within (the|an|one) hour|asap|last chance|"
              r"final reminder|or (we|the shipment|it)\b.{0,25}(cancel\w*|penalt\w*))")
_EN_RULES = r"(instructions?|rules|guidelines|prompt|directives|polic(y|ies)|restrictions|programming)"

# ---- building blocks (Arabic; written naturally, normalised at compile time) ----------------
_AR_BANKISH = r"(الحساب البنكي|حساب بنكي|الحساب الجديد|حساب جديد|الآيبان|ايبان|رقم الحساب|بيانات الحساب|المستفيد|البنك الجديد)"
_AR_CHANGE = r"(تغيير|تغير|تحديث|المحدثة|المحدث|محدث|الجديد|جديد|تعديل|غيّر)"
_AR_PAY = r"(تحويل|التحويل|حوّل|حول المبلغ|الدفعة|الدفع|المبلغ|المبالغ|ادفع|سداد)"
_AR_URGENT = r"(عاجل|فوراً|فورا|الآن|اليوم|خلال ساعة|حالاً|وإلا)"

PATTERNS: dict[str, list[re.Pattern]] = {
    "instruction_override": [
        _rx(r"\b(ignore|disregard|forget|override|bypass)\b.{0,30}?\b(previous|prior|above|earlier|all|your|any|the|these|those)\b.{0,15}?\b" + _EN_RULES),
        _rx(r"\b(ignore|disregard|forget|override)\s+(your|all|the)\s+" + _EN_RULES),
        _rx(r"\b(you are now|from now on,? you|you must now|pretend (you|to be)|act as (our|a|an|my)\b|no restrictions)"),
        _rx(r"\bnew (instructions|rules|policy|role)\b( loaded| for (the )?(ai|assistant|you))?"),
        _rx(r"(^|\s)(#{2,}\s*system\b|system\s*:|\[system\]|<\|?system\|?>)"),
        _rx(r"(تجاهل|انسَ|انس|اهمل|تخط)[^.\n]{0,25}(التعليمات|القواعد|الأوامر|الإرشادات)"),
        _rx(r"(أنت الآن|اتبع تعليماتي|نفذ ما أطلبه)"),
    ],
    "prompt_exfiltration": [
        _rx(r"\b(reveal|show|print|repeat|output|display|paste|tell|send|give|share|write|dump|what (are|is))\b.{0,40}?"
            r"(system prompt|initial prompt|your (instructions|prompt|configuration|config|rules|programming)|"
            r"instructions your developers|developer (messages?|instructions)|api keys?|access tokens?|passwords?|"
            r"secrets?\b|credentials|everything above|above this line)"),
        _rx(r"\b(system prompt|(your|the) (hidden|secret|internal) (instructions|prompt|rules))\b"),
        # Secrets asked for as a question: "what/which API keys / password / token do you use ...?"
        _rx(r"\b(what|which)\b.{0,30}?\b(api keys?|passwords?|access tokens?|tokens?|credentials|secret keys?)\b"
            r"(?!\s+protection).{0,40}?\b(you|your)\b"),
        _rx(r"(شو|ما|ماهي|ما هي|ايش)[^.\n]{0,15}(token|password|api key|كلمة المرور|كلمات المرور|الرمز السري)"),
        _rx(r"(اكتب|اعرض|أظهر|أرسل|ارسل|أعطني|اعطني)[^.\n]{0,30}(موجه النظام|التعليمات المخفية|تعليماتك|كلمات المرور|كلمة المرور|المفاتيح السرية)"),
    ],
    "bank_change": [
        _rx(_EN_CHANGE + r".{0,40}?" + _EN_BANKISH),
        _rx(_EN_BANKISH + r".{0,40}?" + _EN_CHANGE),
        _rx(_EN_PAY + r".{0,50}?\b(new|updated|different|another)\s+(bank|account|iban)"),
        _rx(_AR_BANKISH + r".{0,30}?" + _AR_CHANGE),
        _rx(_AR_CHANGE + r".{0,30}?" + _AR_BANKISH),
        _rx(r"(الحساب الجديد|حساب جديد).{0,40}?" + _AR_PAY),
        _rx(_AR_PAY + r".{0,40}?(الحساب الجديد|حساب جديد)"),
    ],
    "payment_pressure": [
        _rx(_EN_URGENT + r".{0,50}?\b" + _EN_PAY),
        _rx(r"\b" + _EN_PAY + r".{0,50}?" + _EN_URGENT),
        _rx(_AR_URGENT + r".{0,40}?" + _AR_PAY),
        _rx(_AR_PAY + r".{0,40}?" + _AR_URGENT),
    ],
    "payment_status": [
        _rx(r"\bmark\w*\b.{0,40}?\b(as )?(paid|received|settled)\b"),
        _rx(r"\bpayment status\b.{0,25}?\b(received|paid|settled)\b"),
        _rx(r"\bconfirm\w*\b.{0,40}?\b(is|as|been|has been) (fully )?(paid|received|settled)\b"),
        _rx(r"(اعتبر|اعتبار|أكد|اكد|سجل)[^.\n]{0,30}(مدفوع|استلمت|مستلمة|تم الدفع)"),
    ],
    "approval_bypass": [
        _rx(r"\b(without|no need (for|to)|skip\w*|bypass\w*|don'?t (wait|need)|turn off|disable|switch off)\b.{0,30}?"
            r"\b(approv\w*|review\w*|check\w*|confirmation|manager|owner|sign[- ]?off|human)"),
        _rx(r"\bauto[- ]?approv\w*|\bapprove (it|this|them|everything|all|the order)? ?automatically|"
            r"\bautomatic(ally)? (send|dispatch|approv)\w*|\bsend\w*\b.{0,40}?\b(automatically|on your own|by yourself)\b|"
            r"\bauthori[sz]e[ds]? you to (send|approve|reply)|\bon your own without\b"),
        _rx(r"(بدون|دون|من غير|بلا)[^.\n]{0,25}(موافقة|مراجعة|الموافقة|المراجعة|إذن|المدير)"),
        _rx(r"(ارسل|أرسل|وافق)[^.\n]{0,25}تلقائياً"),
    ],
}

# Hidden-instruction signals: where text is embedded, and who it is addressed to.
_CONTEXT = _rx(r"(\[attachment|attachment text|attachment metadata|attachment:|نص المرفق|\[نص|metadata|<!--|"
               r"hidden comment|\(hidden\)|\(white text\)|comment\s*[:=]|files?\s*:|\.pdf\b|\.docx?\b|\.xlsx?\b)")
_ADDRESSEE = _rx(r"(\bassistant\b|\bai agent\b|\bai\s*:|note to (the )?(ai|assistant|agent)|\bthe agent\b|المساعد|للمساعد)")
_HTML_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)
_BLANK_RUN = re.compile(r"\n\s*\n\s*\n\s*\n")


class GuardResult(BaseModel):
    """Flags raised by the rule layer, with the matched text as evidence."""

    flags: list[str] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)      # [{flag, snippet}]


def scan_rules(text: str) -> GuardResult:
    """Run every pattern on every normalised view; add hidden-instruction signals."""
    found: dict[str, str] = {}
    for view in views(text):
        for flag, patterns in PATTERNS.items():
            if flag in found:
                continue
            for pattern in patterns:
                if m := pattern.search(view):
                    found[flag] = m.group(0)[:100]
                    break
    # Payment-status manipulation is also a form of payment pressure (fraud intent).
    if "payment_status" in found and "payment_pressure" not in found:
        found["payment_pressure"] = found["payment_status"]

    # Hidden instructions: embedded/addressed content AND (another attack signal or an AI addressee).
    lowered = views(text)[0]
    in_context = bool(_CONTEXT.search(lowered)) or bool(_BLANK_RUN.search(text))
    addressed = _ADDRESSEE.search(lowered)
    comment_attack = any(re.search(r"\b(ignore|forget|update|send|approve|reveal|print|mark|change)\b", c, re.I)
                         for c in _HTML_COMMENT.findall(text))
    if comment_attack or (in_context and (addressed or found)):
        found["hidden_instruction"] = (addressed.group(0) if addressed else "embedded content")[:100]

    flags = sorted(found)
    return GuardResult(flags=flags, evidence=[{"flag": f, "snippet": found[f]} for f in flags])


def scan(text: str) -> list[str]:
    """Rule-layer flag codes only (sorted). Kept for callers that just need the codes."""
    return scan_rules(text).flags
