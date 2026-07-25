#!/usr/bin/env python3
"""
Deterministic English -> Arabic translation for NGO/UN job listings.

No API, no cost, no hallucination.

Job titles are COMPOSED, not substituted word-by-word, because Arabic is
head-initial and English is head-final:

    Senior  Procurement  Officer     (modifier modifier HEAD)
    موظف    أول          المشتريات   (HEAD modifier modifier)

The title is decomposed into role / seniority / domain / grade, then
reassembled in Arabic order. If no role noun is recognised, the English is
kept unchanged - a partly-English title is fine, a garbled Arabic one is not.

To extend: add entries to the dicts below.
"""
import re

# --------------------------------------------------------------------------
# Organisations
# --------------------------------------------------------------------------
ORGS = {
    "world food programme": "برنامج الأغذية العالمي",
    "world health organization": "منظمة الصحة العالمية",
    "food and agriculture organization": "منظمة الأغذية والزراعة",
    "international organization for migration": "المنظمة الدولية للهجرة",
    "united nations development programme": "برنامج الأمم المتحدة الإنمائي",
    "united nations population fund": "صندوق الأمم المتحدة للسكان",
    "united nations children's fund": "منظمة الأمم المتحدة للطفولة",
    "office for the coordination of humanitarian affairs": "مكتب تنسيق الشؤون الإنسانية",
    "catholic relief services": "منظمة الإغاثة الكاثوليكية",
    "norwegian refugee council": "المجلس النرويجي للاجئين",
    "danish refugee council": "المجلس الدنماركي للاجئين",
    "international rescue committee": "لجنة الإنقاذ الدولية",
    "save the children": "منظمة إنقاذ الطفولة",
    "doctors without borders": "أطباء بلا حدود",
    "medecins sans frontieres": "أطباء بلا حدود",
    "international committee of the red cross": "اللجنة الدولية للصليب الأحمر",
    "world vision": "منظمة الرؤية العالمية",
    "mercy corps": "مؤسسة ميرسي كور",
    "action against hunger": "منظمة العمل ضد الجوع",
    "islamic relief": "الإغاثة الإسلامية",
    "qatar charity": "قطر الخيرية",
    "plan international": "منظمة بلان الدولية",
    "care international": "منظمة كير الدولية",
    "concern worldwide": "منظمة كونسيرن",
    "oxfam": "منظمة أوكسفام",
    "unhcr": "المفوضية السامية للأمم المتحدة لشؤون اللاجئين",
    "unicef": "منظمة الأمم المتحدة للطفولة (اليونيسف)",
    "undp": "برنامج الأمم المتحدة الإنمائي",
    "unfpa": "صندوق الأمم المتحدة للسكان",
    "unops": "مكتب الأمم المتحدة لخدمات المشاريع",
    "unido": "منظمة الأمم المتحدة للتنمية الصناعية",
    "unesco": "منظمة الأمم المتحدة للتربية والعلم والثقافة",
    "ocha": "مكتب تنسيق الشؤون الإنسانية",
    "wfp": "برنامج الأغذية العالمي",
    "who": "منظمة الصحة العالمية",
    "fao": "منظمة الأغذية والزراعة",
    "iom": "المنظمة الدولية للهجرة",
    "icrc": "اللجنة الدولية للصليب الأحمر",
    "msf": "أطباء بلا حدود",
    "nrc": "المجلس النرويجي للاجئين",
    "drc": "المجلس الدنماركي للاجئين",
    "irc": "لجنة الإنقاذ الدولية",
    "crs": "منظمة الإغاثة الكاثوليكية",
}

# --------------------------------------------------------------------------
# ROLE = the head noun. Becomes the first word of the Arabic title.
# --------------------------------------------------------------------------
ROLES = {
    "chief of party": "رئيس المشروع",
    "head of office": "رئيس المكتب",
    "head of mission": "رئيس البعثة",
    "team leader": "قائد فريق",
    "focal point": "منسق",
    "case worker": "أخصائي حالة",
    "social worker": "أخصائي اجتماعي",
    "medical doctor": "طبيب",
    "data entry clerk": "مدخل بيانات",
    "storekeeper": "أمين مخزن",
    "receptionist": "موظف استقبال",
    "coordinator": "منسق",
    "specialist": "أخصائي",
    "supervisor": "مشرف",
    "facilitator": "ميسر",
    "consultant": "استشاري",
    "accountant": "محاسب",
    "enumerator": "باحث ميداني",
    "researcher": "باحث",
    "counsellor": "مرشد نفسي",
    "counselor": "مرشد نفسي",
    "pharmacist": "صيدلي",
    "technician": "فني",
    "electrician": "كهربائي",
    "mechanic": "ميكانيكي",
    "associate": "معاون",
    "assistant": "مساعد",
    "volunteer": "متطوع",
    "developer": "مطور",
    "surveyor": "مساح",
    "engineer": "مهندس",
    "director": "مدير",
    "designer": "مصمم",
    "analyst": "محلل",
    "auditor": "مراجع",
    "manager": "مدير",
    "advisor": "مستشار",
    "adviser": "مستشار",
    "officer": "موظف",
    "trainer": "مدرب",
    "cashier": "أمين صندوق",
    "midwife": "قابلة",
    "editor": "محرر",
    "intern": "متدرب",
    "driver": "سائق",
    "doctor": "طبيب",
    "nurse": "ممرض",
    "guard": "حارس",
    "clerk": "كاتب",
    "cleaner": "عامل نظافة",
    "lead": "قائد",
}

# --------------------------------------------------------------------------
# SENIORITY = modifier placed immediately after the role noun.
# --------------------------------------------------------------------------
SENIORITY = {
    "senior": "أول",
    "chief": "رئيسي",
    "deputy": "نائب",
    "junior": "مساعد",
    "principal": "رئيسي",
    "national": "وطني",
    "international": "دولي",
    "regional": "إقليمي",
    "field": "ميداني",
    "roving": "متنقل",
    "temporary": "مؤقت",
}

# --------------------------------------------------------------------------
# DOMAIN = subject area, placed last.
# --------------------------------------------------------------------------
DOMAINS = {
    "monitoring, evaluation, accountability and learning": "الرصد والتقييم والمساءلة والتعلم",
    "monitoring and evaluation": "الرصد والتقييم",
    "monitoring & evaluation": "الرصد والتقييم",
    "water, sanitation and hygiene": "المياه والإصحاح والنظافة",
    "food security and livelihoods": "الأمن الغذائي وسبل العيش",
    "gender based violence": "الحماية من العنف القائم على النوع الاجتماعي",
    "gender-based violence": "الحماية من العنف القائم على النوع الاجتماعي",
    "sexual and reproductive health": "الصحة الجنسية والإنجابية",
    "community mobilization": "التعبئة المجتمعية",
    "information management": "إدارة المعلومات",
    "information technology": "تقنية المعلومات",
    "business development": "تطوير الأعمال",
    "emergency response": "الاستجابة الطارئة",
    "capacity building": "بناء القدرات",
    "grants management": "إدارة المنح",
    "risk management": "إدارة المخاطر",
    "case management": "إدارة الحالة",
    "cash transfer": "التحويلات النقدية",
    "child protection": "حماية الطفل",
    "human resources": "الموارد البشرية",
    "supply chain": "سلسلة الإمداد",
    "mental health": "الصحة النفسية",
    "public health": "الصحة العامة",
    "programme quality": "جودة البرامج",
    "program quality": "جودة البرامج",
    "psychosocial support": "الدعم النفسي والاجتماعي",
    "food security": "الأمن الغذائي",
    "data entry": "إدخال البيانات",
    "procurement": "المشتريات",
    "communications": "الاتصال",
    "administration": "الشؤون الإدارية",
    "psychosocial": "الدعم النفسي والاجتماعي",
    "livelihoods": "سبل العيش",
    "partnerships": "الشراكات",
    "agriculture": "الزراعة",
    "protection": "الحماية",
    "compliance": "الامتثال",
    "nutrition": "التغذية",
    "education": "التعليم",
    "logistics": "اللوجستيات",
    "reporting": "إعداد التقارير",
    "operations": "العمليات",
    "emergency": "الطوارئ",
    "warehouse": "المخازن",
    "database": "قواعد البيانات",
    "advocacy": "المناصرة",
    "security": "الأمن",
    "shelter": "المأوى",
    "finance": "الشؤون المالية",
    "accounting": "المحاسبة",
    "project": "المشاريع",
    "programme": "البرامج",
    "program": "البرامج",
    "health": "الصحة",
    "legal": "الشؤون القانونية",
    "audit": "المراجعة",
    "fleet": "الأسطول",
    "wash": "المياه والإصحاح والنظافة",
    "gbv": "الحماية من العنف القائم على النوع الاجتماعي",
    "meal": "الرصد والتقييم والمساءلة والتعلم",
    "m&e": "الرصد والتقييم",
    "hr": "الموارد البشرية",
    "ict": "تقنية المعلومات والاتصالات",
    "it": "تقنية المعلومات",
}

PLACES = {
    "khartoum north": "الخرطوم بحري",
    "khartoum bahri": "الخرطوم بحري",
    "aljazeera madani": "ود مدني، الجزيرة",
    "al jazeera madani": "ود مدني، الجزيرة",
    "wad madani": "ود مدني",
    "wad medani": "ود مدني",
    "central darfur": "وسط دارفور",
    "north darfur": "شمال دارفور",
    "south darfur": "جنوب دارفور",
    "west darfur": "غرب دارفور",
    "east darfur": "شرق دارفور",
    "south kordofan": "جنوب كردفان",
    "north kordofan": "شمال كردفان",
    "west kordofan": "غرب كردفان",
    "northern state": "الولاية الشمالية",
    "multiple locations": "مواقع متعددة",
    "port sudan": "بورتسودان",
    "blue nile": "النيل الأزرق",
    "white nile": "النيل الأبيض",
    "river nile": "نهر النيل",
    "el geneina": "الجنينة",
    "al geneina": "الجنينة",
    "ed damazin": "الدمازين",
    "el fasher": "الفاشر",
    "al fasher": "الفاشر",
    "ed daein": "الضعين",
    "el daein": "الضعين",
    "al qadarif": "القضارف",
    "red sea": "البحر الأحمر",
    "el obeid": "الأبيض",
    "al obeid": "الأبيض",
    "omdurman": "أم درمان",
    "zalingei": "زالنجي",
    "khartoum": "الخرطوم",
    "damazin": "الدمازين",
    "kordofan": "كردفان",
    "gedaref": "القضارف",
    "kadugli": "كادقلي",
    "dongola": "دنقلا",
    "kassala": "كسلا",
    "atbara": "عطبرة",
    "darfur": "دارفور",
    "gezira": "الجزيرة",
    "sennar": "سنار",
    "shendi": "شندي",
    "aljazeera": "الجزيرة",
    "nyala": "نيالا",
    "kosti": "كوستي",
    "singa": "سنجة",
    "rabak": "ربك",
    "sudan": "السودان",
    "remote": "عن بعد",
}

MONTHS = {
    "january": "يناير", "february": "فبراير", "march": "مارس",
    "april": "أبريل", "may": "مايو", "june": "يونيو",
    "july": "يوليو", "august": "أغسطس", "september": "سبتمبر",
    "october": "أكتوبر", "november": "نوفمبر", "december": "ديسمبر",
    "jan": "يناير", "feb": "فبراير", "mar": "مارس", "apr": "أبريل",
    "jun": "يونيو", "jul": "يوليو", "aug": "أغسطس", "sept": "سبتمبر",
    "sep": "سبتمبر", "oct": "أكتوبر", "nov": "نوفمبر", "dec": "ديسمبر",
}

# grade codes preserved verbatim: G-6, GS5, NOA, P-3, SB-4
GRADE_RE = re.compile(
    r"\b(?:GS|NO|SB|SC|IC|FS|G|P)[\s\-]?\d{1,2}\b|\bNO[A-E]\b", re.I)


def _sub_all(text, table):
    if not text:
        return text, 0
    hits = 0
    for en in sorted(table, key=len, reverse=True):
        pat = re.compile(r"(?<![A-Za-z])" + re.escape(en) + r"(?![A-Za-z])", re.I)
        text, n = pat.subn(table[en], text)
        hits += n
    return text, hits


def _find_first(text, table):
    for en in sorted(table, key=len, reverse=True):
        if re.search(r"(?<![A-Za-z])" + re.escape(en) + r"(?![A-Za-z])", text, re.I):
            return table[en], en
    return None, None


def _strip(text, phrase):
    return re.sub(r"(?<![A-Za-z])" + re.escape(phrase) + r"(?![A-Za-z])",
                  " ", text, flags=re.I)


def translate_title(s):
    """Compose Arabic title head-initial. Returns (arabic, ok)."""
    if not s:
        return s, False

    work = s
    grades = GRADE_RE.findall(work)
    work = GRADE_RE.sub(" ", work)
    work = re.sub(r"\([^)]*\)", " ", work)

    role, role_en = _find_first(work, ROLES)
    if not role:
        return s, False
    work = _strip(work, role_en)

    senior, senior_en = _find_first(work, SENIORITY)
    if senior:
        work = _strip(work, senior_en)

    domains = []
    remaining = work
    while len(domains) < 2:
        dom, dom_en = _find_first(remaining, DOMAINS)
        if not dom:
            break
        domains.append(dom)
        remaining = _strip(remaining, dom_en)

    parts = [role]
    if senior:
        parts.append(senior)
    parts.extend(domains)

    out = " ".join(parts)
    if grades:
        out += " " + " ".join(g.upper().replace(" ", "-") for g in grades)

    leftover = re.sub(r"[^A-Za-z ]", " ", remaining).strip()
    leftover = re.sub(r"\s+", " ", leftover)
    if len(leftover) > 3 and leftover.lower() not in ("and", "for", "the", "of"):
        out += f" ({leftover})"

    return out, True


def translate_org(s):
    out, hits = _sub_all(s, ORGS)
    return out, bool(hits)


def translate_place(s):
    out, hits = _sub_all(s, PLACES)
    return out.replace(",", "،"), bool(hits)


def translate_date(s):
    out, _ = _sub_all(s, MONTHS)
    return out


def enrich(j):
    """Fill *_ar fields. Hand-written overrides in manual.json always win."""
    if not j.get("title_ar"):
        ar, ok = translate_title(j["title"])
        j["title_ar"] = ar if ok else ""
    if not j.get("org_ar"):
        ar, ok = translate_org(j["org"])
        j["org_ar"] = ar if ok else ""
    if not j.get("location_ar"):
        ar, ok = translate_place(j["location"])
        j["location_ar"] = ar if ok else ""
    if not j.get("closing_ar"):
        j["closing_ar"] = translate_date(j["closing"])
    return j
