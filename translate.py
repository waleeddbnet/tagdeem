
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
    "sos children's villages": "منظمة القرى الأطفال",
    "sos childrens villages": "قرى الأطفال",
    "premiere urgence internationale": "بروميير أورجونس الدولية",
    "premiere urgence": "بروميير أورجونس",
    "relief international": "منظمة الإغاثة الدولية",
    "solidarites international": "سوليدارتيه الدولية",
    "triangle generation humanitaire": "منظمة ترايانغل",
    "people in need": "منظمة الناس في حاجة",
    "cooperazione internazionale": "منظمة كوبي الدولية",
    "handicap international": "منظمة الإعاقة الدولية",
    "humanity & inclusion": "منظمة الإنسانية والإدماج",
    "malteser international": "منظمة مالتيزر الدولية",
    "war child": "منظمة أطفال الحرب",
    "alight": "منظمة ألايت",
    "zoa": "منظمة زوا",
    "acted": "منظمة أكتد",
    "international medical corps": "الهيئة الطبية الدولية",
    "medecins sans frontieres holland": "أطباء بلا حدود - هولندا",
    "medecins sans frontieres switzerland": "أطباء بلا حدود - سويسرا",
    "msf holland": "أطباء بلا حدود - هولندا",
    "msf switzerland": "أطباء بلا حدود - سويسرا",
    "msf belgium": "أطباء بلا حدود - بلجيكا",
    "msf france": "أطباء بلا حدود - فرنسا",
    "save the children international": "منظمة إنقاذ الطفولة الدولية",
    "zoa international": "منظمة زوا الدولية",
    "tgh": "منظمة ترايانغل",
    "sci": "منظمة إنقاذ الطفولة",
    "unv": "متطوعو الأمم المتحدة",
    "united nations volunteers": "متطوعو الأمم المتحدة",
    "unitams": "بعثة الأمم المتحدة المتكاملة في السودان",
    "hac": "مفوضية العون الإنساني",
    "british embassy": "السفارة البريطانية",
    "dal food": "مجموعة دال للأغذية",
    "dal group": "مجموعة دال",
    "ctc group": "مجموعة سي تي سي",
    "care international in sudan": "منظمة كير الدولية",
    "care international": "منظمة كير الدولية",
    "norwegian church aid": "المعونة الكنسية النرويجية",
    "danchurchaid": "المعونة الكنسية الدنماركية",
    "dan church aid": "المعونة الكنسية الدنماركية",
    "sudanese red crescent society": "الهلال الأحمر السوداني",
    "sudanese red crescent": "الهلال الأحمر السوداني",
    "medecins sans frontieres belgium": "أطباء بلا حدود - بلجيكا",
    "medecins sans frontieres switzerland": "أطباء بلا حدود - سويسرا",
    "medecins sans frontieres spain": "أطباء بلا حدود - إسبانيا",
    "medecins sans frontieres france": "أطباء بلا حدود - فرنسا",
    "world vision international": "منظمة الرؤية العالمية",
    "medecins sans frontieres belgium": "أطباء بلا حدود - بلجيكا",
    "medecins sans frontieres spain": "أطباء بلا حدود - إسبانيا",
    "msf belgium": "أطباء بلا حدود - بلجيكا",
    "msf spain": "أطباء بلا حدود - إسبانيا",
    "norwegian church aid": "المعونة الكنسية النرويجية",
    "danchurchaid": "المعونة الكنسية الدنماركية",
    "sudanese red crescent society": "الهلال الأحمر السوداني",
    "sudanese red crescent": "الهلال الأحمر السوداني",
    "world vision international": "منظمة الرؤية العالمية",
    "care international in sudan": "منظمة كير الدولية",
    "save the children international": "منظمة إنقاذ الطفولة",
    "relief international": "منظمة الإغاثة الدولية",
    "sudani": "سوداني",
    "zain": "زين",
    "mtn": "إم تي إن",
    "bank of khartoum": "بنك الخرطوم",
}

# --------------------------------------------------------------------------
# ROLE = the head noun. Becomes the first word of the Arabic title.
# --------------------------------------------------------------------------
ROLES = {
    "chief of party": "رئيس المشروع",
    "head of office": "رئيس المكتب",
    "head of mission": "رئيس البعثة",
    "head of programmes": "رئيس البرامج",
    "head of programs": "رئيس البرامج",
    "head of department": "رئيس القسم",
    "head of unit": "رئيس الوحدة",
    "head of": "رئيس",
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
    "paediatrician": "طبيب أطفال",
    "pediatrician": "طبيب أطفال",
    "gynaecologist": "طبيب نساء وتوليد",
    "anaesthetist": "طبيب تخدير",
    "radiographer": "فني أشعة",
    "physiotherapist": "أخصائي علاج طبيعي",
    "nutritionist": "أخصائي تغذية",
    "epidemiologist": "أخصائي أوبئة",
    "laboratory technician": "فني مختبر",
    "lab technician": "فني مختبر",
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
    "teacher": "معلم",
    "principal": "مدير مدرسة",
    "vice principal": "نائب مدير مدرسة",
    "head teacher": "مدير مدرسة",
    "headmaster": "مدير مدرسة",
    "librarian": "أمين مكتبة",
    "lecturer": "محاضر",
    "tutor": "مدرس خصوصي",
    "professional": "أخصائي",
    "agent": "موظف",
    "call center agent": "موظف مركز اتصال",
    "generalist": "أخصائي عام",
    "architect": "مهندس معماري",
    "administrator": "مسؤول",
    "representative": "مندوب",
    "planner": "مخطط",
    "controller": "مراقب",
    "operator": "مشغل",
    "welder": "لحام",
    "carpenter": "نجار",
    "plumber": "سباك",
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
    "data center operations": "عمليات مراكز البيانات",
    "infrastructure management": "إدارة البنية التحتية",
    "business assurance": "ضمان الأعمال",
    "strategic communications": "الاتصال المؤسسي",
    "general ledger": "الأستاذ العام",
    "cloud": "الحوسبة السحابية",
    "infrastructure": "البنية التحتية",
    "network": "الشبكات",
    "networks": "الشبكات",
    "telecom": "الاتصالات",
    "marketing": "التسويق",
    "sales": "المبيعات",
    "billing": "الفوترة",
    "revenue": "الإيرادات",
    "budgeting": "الميزانية",
    "treasury": "الخزينة",
    "tax": "الضرائب",
    "power": "الطاقة",
    "workshop": "الورشة",
    "contact center": "مركز الاتصال",
    "call center": "مركز الاتصال",
    "customer service": "خدمة العملاء",
    "customer experience": "تجربة العملاء",
    "measurement": "القياس",
    "creative arts": "الفنون الإبداعية",
    "pmo": "مكتب إدارة المشاريع",
    "geo": "النظم الجغرافية",
    "humanitarian": "الشؤون الإنسانية",
    "pharmacy": "الصيدلة",
    "midwifery": "القبالة",
    "primary health care": "الرعاية الصحية الأولية",
    "preschool": "مرحلة الروضة",
    "kindergarten": "رياض الأطفال",
    "primary": "المرحلة الابتدائية",
    "secondary": "المرحلة الثانوية",
    "english": "اللغة الإنجليزية",
    "arabic": "اللغة العربية",
    "mathematics": "الرياضيات",
    "math": "الرياضيات",
    "maths": "الرياضيات",
    "science": "العلوم",
    "religion": "التربية الإسلامية",
    "islamic studies": "التربية الإسلامية",
    "physical education": "التربية البدنية",
    "art": "التربية الفنية",
    "global perspectives": "المنظورات العالمية",
    "class": "الفصل",
    "purchasing": "المشتريات",
    "pharmacy": "الصيدلية",
    "transport": "النقل",
    "customs": "الجمارك",
    "custom": "الجمارك",
    "voucher": "القسائم",
    "cash and voucher": "النقد والقسائم",
    "stock": "المخزون",
    "store": "المخازن",
    "watsan": "المياه والإصحاح",
    "biomedical": "الأجهزة الطبية",
    "referral": "الإحالة",
    "outreach": "التوعية المجتمعية",
    "ward": "العنبر",
    "clinical": "الرعاية السريرية",
    "sterilization": "التعقيم",
    "laundry": "المغسلة",
    "kitchen": "المطبخ",
    "country": "القطري",
    "liaison": "الاتصال",
    "government": "الحكومي",
    "training": "التدريب",
    "quality": "الجودة",
    "gender": "النوع الاجتماعي",
    "youth": "الشباب",
    "disability": "الإعاقة",
    "environment": "البيئة",
    "energy": "الطاقة",
    "media": "الإعلام",
    "office": "المكتب",
    "safety": "السلامة",
    "records": "السجلات",
    "assets": "الأصول",
    "budget": "الميزانية",
    "payroll": "الرواتب",
    "recruitment": "التوظيف",
}

PLACES = {
    "khartoum north": "الخرطوم بحري",
    "khartoum bahri": "الخرطوم بحري",
    "aljazeera madani": "ود مدني، الجزيرة",
    "al jazeera madani": "ود مدني، الجزيرة",
    "wad madani": "ود مدني",
    "madani": "ود مدني",
    "karari": "كرري",
    "aroma": "أروما",
    "damazin": "الدمازين",
    "geneina": "الجنينة",
    "fasher": "الفاشر",
    "obeid": "الأبيض",
    "daein": "الضعين",
    "kabkabiya": "كبكابية",
    "tawila": "الطويلة",
    "gadarif": "القضارف",
    "halfa": "حلفا",
    "merowe": "مروي",
    "abyei": "أبيي",
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

    # prefixes that must precede the role noun in Arabic
    prefix = suffix = ""
    if re.search(r"(?<![A-Za-z])deputy(?![A-Za-z])", work, re.I):
        prefix = "نائب"
        work = _strip(work, "deputy")
    if re.search(r"(?<![A-Za-z])acting(?![A-Za-z])", work, re.I):
        suffix = "بالإنابة"
        work = _strip(work, "acting")

    role, role_en = _find_first(work, ROLES)
    if not role:
        return s, False
    work = _strip(work, role_en)

    senior, senior_en = _find_first(work, SENIORITY)
    if senior:
        work = _strip(work, senior_en)

    domains = []
    remaining = work
    while len(domains) < 3:
        dom, dom_en = _find_first(remaining, DOMAINS)
        if not dom:
            break
        domains.append(dom)
        remaining = _strip(remaining, dom_en)

    parts = [role]
    if senior:
        parts.append(senior)
    head = " ".join(parts)

    if domains:
        head += " " + " - ".join(domains)
    out = head

    # "deputy" is a construct-state prefix in Arabic, not a suffix modifier
    if prefix:
        out = prefix + " " + out
    if suffix:
        out = out + " " + suffix
    if grades:
        out += " " + " ".join(g.upper().replace(" ", "-") for g in grades)

    # Untranslated English fragments are noise on an Arabic card, so they are
    # dropped rather than shown in brackets. The English title is still in the
    # caption for anyone searching for it.
    return out, True


_ORG_TAIL = re.compile(
    r"\s*[-–|,]?\s*(sudan|south sudan|khartoum|sd|international|"
    r"belgium|switzerland|spain|holland|netherlands|france|germany|"
    r"uk|usa|worldwide|global|ltd|limited|inc)\s*$", re.I)


def translate_org(s):
    # try the full name first - "MSF Belgium" is a distinct entity from "MSF"
    direct, hits = _sub_all(s, ORGS)
    if hits and not re.search(r"[A-Za-z]{2,}", direct):
        return direct.strip(), True

    t = s
    for _ in range(3):
        t2 = _ORG_TAIL.sub("", t).strip(" -–,|")
        if t2 == t:
            break
        t = t2
    out, hits = _sub_all(t, ORGS)
    # any English left after translating is noise, not information
    if hits:
        out = re.sub(r"[A-Za-z]{2,}", "", out)
        out = re.sub(r"\s{2,}", " ", out).strip(" -–,|()")
    return out, bool(hits)


def translate_place(s):
    out, hits = _sub_all(s, PLACES)
    return out.replace(",", "،"), bool(hits)


_AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
              "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def translate_date(s):
    """Arabic month names. Numeric dd/mm/yyyy is expanded first."""
    if not s:
        return s
    m = re.match(r"^\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= mo <= 12:
            return f"{d} {_AR_MONTHS[mo-1]} {y}"
    # "Jul 24, 2026" / "August 6, 2026"  ->  "24 يوليو 2026"
    m = re.match(r"^\s*([A-Za-z]{3,9})\s+(\d{1,2}),?\s*(\d{4})", s)
    if m:
        mon = MONTHS.get(m.group(1).lower())
        if mon:
            return f"{int(m.group(2))} {mon} {m.group(3)}"
    out, _ = _sub_all(s, MONTHS)
    # any dd/mm/yyyy still embedded in the string
    def _rep(m):
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        return f"{d} {_AR_MONTHS[mo-1]} {y}" if 1 <= mo <= 12 else m.group(0)
    out = re.sub(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", _rep, out)
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
