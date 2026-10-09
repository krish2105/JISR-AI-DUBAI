/**
 * dictionaries.ts — Every user-facing string, in English and Arabic.
 *
 * Why: one typed object per language. TypeScript forces the Arabic dictionary to have
 * exactly the same keys as English, so no screen can silently miss a translation.
 * Numbers, currency codes and HS codes stay in Western digits inside Arabic text
 * (they are wrapped in <bdi> where they appear).
 */

import type { Locale } from "./config";

const en = {
  brand: { name: "Jisr", tagline: "The governed bridge for India–UAE trade" },
  nav: { home: "Overview", demo: "Live demo", approvals: "Approvals", audit: "Audit log" },
  theme: { toLight: "Switch to light theme", toDark: "Switch to dark theme" },
  lang: { switchLabel: "العربية", switchAria: "Switch language to Arabic" },
  landing: {
    eyebrow: "Create AI Agents Championship · Best Business AI Agent",
    title: "From buyer enquiry to approved quote — every crossing governed.",
    subtitle:
      "Jisr turns an India-to-UAE enquiry into a priced INR/AED quote, a cited CEPA duty check, an export document pack and bilingual replies. Humans approve anything that leaves the building.",
    cta: "Run the live demo",
    secondary: "Open approval inbox",
    pillars: [
      { title: "Governed", body: "A deterministic policy engine sits between the agents and the world. Even a fooled model cannot send or change bank details." },
      { title: "Cited", body: "Tariff and origin facts come only from official documents, with dates — or are flagged for a human." },
      { title: "Bilingual", body: "Arabic and English drafts in the buyer's language, right-to-left done properly." },
    ],
    status: "Phase 1 build: the full path works end to end; specialist agents are being deepened phase by phase.",
  },
  demo: {
    title: "Live demo",
    subtitle: "Pick an enquiry and watch the agents work. Nothing leaves without your approval.",
    samples: "Sample enquiries",
    hostileHint: "Tries to change bank details",
    custom: "Or paste your own enquiry",
    customPlaceholder: "e.g. We need 300 pcs brass lamps, CIF Jebel Ali, delivery by 20 Dec…",
    runCustom: "Run",
    running: "Agents working…",
    graph: "Agent graph",
    timeline: "Timeline",
    emptyTimeline: "Start a run to see each step here.",
    counters: {
      risks: "Risks caught",
      steps: "Steps",
      pending: "Awaiting you",
      time: "Agent time",
      aed: "AED saved",
      aedNote: "CEPA duty optimiser arrives in Phase 5",
    },
    result: {
      quote: "Quote",
      item: "Item",
      qty: "Qty",
      unitAed: "Unit (AED)",
      totalAed: "Total (AED)",
      totalInr: "Total (INR)",
      fx: "FX",
      draft: "Reply draft",
      approve: "Approve & send",
      reject: "Reject",
      edit: "Edit before sending",
      approved: "Approved — sent via simulator",
      rejected: "Rejected — nothing was sent",
      blockedTitle: "Blocked by policy",
      blockedBody: "The governance engine refused this action. It was logged in the audit chain.",
      openInbox: "Open in approval inbox",
      openAudit: "See audit entry",
      message: "Message (personal data masked)",
    },
    stub: "stub",
    needsHumanCheck: "needs human check",
  },
  agents: {
    ingest: "Ingest", guard: "Guard", supervisor: "Supervisor", quote: "Quote", duty: "CEPA duty",
    docs: "Documents", trust: "Buyer trust", outreach: "Outreach", governance: "Governance",
    human: "You", system: "System", channel: "Channel",
  } as Record<string, string>,
  kinds: {
    run_started: "Run started", agent_started: "started", agent_finished: "finished", plan: "Plan",
    tool_call: "Tool call", tool_result: "Tool result", retrieval_attempt: "Retrieval",
    policy_decision: "Policy decision", approval_needed: "Waiting for approval", approval_decided: "Decision",
    blocked: "Blocked", error: "Error", done: "Done",
  } as Record<string, string>,
  status: {
    new: "New", planning: "Planning", needs_approval: "Needs approval", approved: "Approved", sent: "Sent",
    blocked: "Blocked", done: "Done",
  } as Record<string, string>,
  risk: { low: "Low risk", medium: "Medium risk", high: "High risk" } as Record<string, string>,
  approvals: {
    title: "Approval inbox",
    subtitle: "Everything an agent wants to send waits here. Approve, edit or reject.",
    empty: "Nothing waiting. Run the demo to create an approval.",
    reason: "Why",
    evidence: "Evidence",
    rule: "Policy rule",
    history: "Recently decided",
    run: "Run",
  },
  audit: {
    title: "Audit log",
    subtitle: "Append-only and hash-chained: editing or deleting any row breaks the chain.",
    verified: "Chain verified",
    broken: "Chain broken",
    entries: "entries",
    time: "Time",
    actor: "Actor",
    action: "Action",
    run: "Run",
    hash: "Hash",
    empty: "No entries yet.",
  },
  common: { loading: "Loading…", error: "Could not reach the Jisr API. Is it running on port 8000?", retry: "Retry" },
};

export type Dictionary = typeof en;

const ar: Dictionary = {
  brand: { name: "جسر", tagline: "الجسر المحوكم للتجارة بين الهند والإمارات" },
  nav: { home: "نظرة عامة", demo: "عرض مباشر", approvals: "الموافقات", audit: "سجل التدقيق" },
  theme: { toLight: "التبديل إلى الوضع الفاتح", toDark: "التبديل إلى الوضع الداكن" },
  lang: { switchLabel: "English", switchAria: "Switch language to English" },
  landing: {
    eyebrow: "بطولة صناعة وكلاء الذكاء الاصطناعي · أفضل وكيل ذكاء اصطناعي للأعمال",
    title: "من استفسار المشتري إلى عرض سعر معتمد — وكل عبور محكوم.",
    subtitle:
      "يحوّل جسر استفسار المشتري من الهند إلى الإمارات إلى عرض سعر بالروبية والدرهم، وفحص رسوم جمركية موثّق وفق اتفاقية الشراكة الاقتصادية الشاملة، وحزمة مستندات تصدير، وردود ثنائية اللغة. ويوافق الإنسان على كل ما يخرج من الشركة.",
    cta: "شغّل العرض المباشر",
    secondary: "افتح صندوق الموافقات",
    pillars: [
      { title: "محوكم", body: "محرك سياسات حتمي يقف بين الوكلاء والعالم الخارجي. حتى النموذج المخدوع لا يستطيع الإرسال أو تغيير بيانات البنك." },
      { title: "موثّق", body: "معلومات التعريفة وقواعد المنشأ تأتي فقط من الوثائق الرسمية مع تواريخها — أو تُحال إلى إنسان." },
      { title: "ثنائي اللغة", body: "مسودات بالعربية والإنجليزية بلغة المشتري، مع اتجاه صحيح من اليمين إلى اليسار." },
    ],
    status: "بناء المرحلة الأولى: المسار الكامل يعمل من البداية إلى النهاية، ويتم تعميق الوكلاء المتخصصين مرحلة بعد أخرى.",
  },
  demo: {
    title: "عرض مباشر",
    subtitle: "اختر استفساراً وشاهد الوكلاء يعملون. لا شيء يخرج دون موافقتك.",
    samples: "استفسارات نموذجية",
    hostileHint: "يحاول تغيير بيانات البنك",
    custom: "أو الصق استفسارك",
    customPlaceholder: "مثال: نحتاج 300 مصباح نحاسي، CIF جبل علي، التسليم قبل 20 ديسمبر…",
    runCustom: "تشغيل",
    running: "الوكلاء يعملون…",
    graph: "خريطة الوكلاء",
    timeline: "الخط الزمني",
    emptyTimeline: "ابدأ تشغيلاً لرؤية كل خطوة هنا.",
    counters: {
      risks: "مخاطر تم رصدها",
      steps: "خطوات",
      pending: "بانتظارك",
      time: "وقت الوكلاء",
      aed: "درهم تم توفيره",
      aedNote: "محسّن الرسوم الجمركية يصل في المرحلة الخامسة",
    },
    result: {
      quote: "عرض السعر",
      item: "الصنف",
      qty: "الكمية",
      unitAed: "سعر الوحدة (درهم)",
      totalAed: "الإجمالي (درهم)",
      totalInr: "الإجمالي (روبية)",
      fx: "سعر الصرف",
      draft: "مسودة الرد",
      approve: "موافقة وإرسال",
      reject: "رفض",
      edit: "تعديل قبل الإرسال",
      approved: "تمت الموافقة — أُرسل عبر المحاكي",
      rejected: "تم الرفض — لم يُرسل شيء",
      blockedTitle: "محظور بموجب السياسة",
      blockedBody: "رفض محرك الحوكمة هذا الإجراء، وتم تسجيله في سلسلة التدقيق.",
      openInbox: "افتح في صندوق الموافقات",
      openAudit: "اعرض سجل التدقيق",
      message: "الرسالة (البيانات الشخصية مخفية)",
    },
    stub: "تجريبي",
    needsHumanCheck: "يحتاج مراجعة بشرية",
  },
  agents: {
    ingest: "الاستقبال", guard: "الحارس", supervisor: "المشرف", quote: "التسعير", duty: "الرسوم (CEPA)",
    docs: "المستندات", trust: "ثقة المشتري", outreach: "التواصل", governance: "الحوكمة",
    human: "أنت", system: "النظام", channel: "القناة",
  },
  kinds: {
    run_started: "بدأ التشغيل", agent_started: "بدأ", agent_finished: "انتهى", plan: "الخطة",
    tool_call: "استدعاء أداة", tool_result: "نتيجة أداة", retrieval_attempt: "استرجاع",
    policy_decision: "قرار السياسة", approval_needed: "بانتظار الموافقة", approval_decided: "القرار",
    blocked: "محظور", error: "خطأ", done: "اكتمل",
  },
  status: {
    new: "جديد", planning: "تخطيط", needs_approval: "بانتظار الموافقة", approved: "معتمد", sent: "أُرسل",
    blocked: "محظور", done: "اكتمل",
  },
  risk: { low: "مخاطر منخفضة", medium: "مخاطر متوسطة", high: "مخاطر عالية" },
  approvals: {
    title: "صندوق الموافقات",
    subtitle: "كل ما يريد الوكيل إرساله ينتظر هنا. وافق أو عدّل أو ارفض.",
    empty: "لا شيء بانتظارك. شغّل العرض لإنشاء طلب موافقة.",
    reason: "السبب",
    evidence: "الأدلة",
    rule: "قاعدة السياسة",
    history: "قرارات حديثة",
    run: "التشغيل",
  },
  audit: {
    title: "سجل التدقيق",
    subtitle: "سجل إلحاقي فقط ومتسلسل بالتجزئة: أي تعديل أو حذف يكسر السلسلة.",
    verified: "السلسلة سليمة",
    broken: "السلسلة مكسورة",
    entries: "إدخالات",
    time: "الوقت",
    actor: "الفاعل",
    action: "الإجراء",
    run: "التشغيل",
    hash: "التجزئة",
    empty: "لا توجد إدخالات بعد.",
  },
  common: { loading: "جارٍ التحميل…", error: "تعذّر الوصول إلى واجهة جسر. هل تعمل على المنفذ 8000؟", retry: "إعادة المحاولة" },
};

const DICTIONARIES: Record<Locale, Dictionary> = { en, ar };

/** Return the dictionary for a locale. */
export function getDictionary(locale: Locale): Dictionary {
  return DICTIONARIES[locale];
}
