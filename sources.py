#!/usr/bin/env python3
"""
Job sources. To add a site:

    @source("myorg")
    def myorg():
        return [job("myorg", ext_id, title, org, location, closing, url), ...]

Every source returns a list of normalized job dicts. Nothing downstream
(translation, image rendering, posting) needs to know where a job came from.

Preference order when adding an org career site:
    1. ATS JSON endpoint  (Greenhouse / Workday / SuccessFactors / Oracle)
    2. RSS or Atom feed
    3. HTML scrape (last resort - breaks on redesign)
"""
import hashlib
import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; job-relay/1.0)"}

# ReliefWeb requires a pre-approved appname since Nov 2025. Request one at
# https://reliefweb.int/help/api then put it here and set enabled=True below.
RELIEFWEB_APPNAME = "tagdeem"
TIMEOUT = 30

SOURCES = {}


def source(name, enabled=True):
    def deco(fn):
        SOURCES[name] = {"fn": fn, "enabled": enabled}
        return fn
    return deco


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _canon_org(org):
    """Map an org name to its canonical form so 'CRS' and 'Catholic Relief
    Services' fingerprint identically. Falls back to the raw name."""
    try:
        import translate
        ar, ok = translate.translate_org(org)
        if ok:
            return ar
    except Exception:
        pass
    return _norm(org)


def job(src, ext_id, title, org, location, closing, url, org_slug=""):
    """Normalized record. `fp` is a cross-source fingerprint for dedup."""
    fp = hashlib.sha1(
        f"{_canon_org(org)}|{_norm(title)}|{_norm(closing)}".encode()
    ).hexdigest()[:16]
    return {
        "source": src,
        "ext_id": str(ext_id),
        "key": f"{src}:{ext_id}",
        "fp": fp,
        "title": title.strip(),
        "org": org.strip(" -|"),
        "org_slug": org_slug or _norm(org)[:24],
        "location": location.strip().rstrip(". "),
        "closing": closing.strip(),
        "url": url.rstrip("/"),
    }


_DATE_FORMATS = [
    "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
]


def parse_closing(s):
    """Parse a closing date string. Returns date or None if unparseable."""
    if not s:
        return None
    t = re.sub(r"[,]", " ", s).strip()
    t = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", t, flags=re.I)
    t = re.sub(r"\s+", " ", t)
    for f in _DATE_FORMATS:
        try:
            return datetime.strptime(t, f).date()
        except ValueError:
            continue
    return None


def valid(j):
    """Never publish a partial record, or one whose deadline has passed.

    A missing closing date is tolerated - some sites (e.g. corporate career
    pages) simply do not publish one. A closing date that is present but in
    the past is always rejected.
    """
    if not all([j["title"], j["org"]]):
        return False
    if not j["closing"]:
        return True

    d = parse_closing(j["closing"])
    if d is None:
        # unparseable date - post it, the text is shown verbatim anyway
        return True
    if d < date.today():
        print(f"  EXPIRED {j['key']} closed {d}")
        return False
    return True


# --------------------------------------------------------------------------
# sudanjob.net - HTML scrape
# --------------------------------------------------------------------------
@source("sudanjob")
def sudanjob():
    html = requests.get("https://sudanjob.net/", headers=UA, timeout=TIMEOUT).text
    soup = BeautifulSoup(html, "html.parser")
    out = []

    for a in soup.find_all("a", href=re.compile(r"jobview\.php\?id=\d+")):
        m = re.search(r"id=(\d+)", a["href"])
        title = a.get_text(" ", strip=True)
        if not m or not title or title.lower() == "view":
            continue

        row = a.find_parent("tr") or a.parent
        tail = row.get_text(" ", strip=True).split(title, 1)[-1]

        org = tail.split("Location:")[0] if "Location:" in tail else ""
        loc = closing = ""
        if "Closing date:" in tail:
            loc = tail.split("Location:")[-1].split("Closing date:")[0]
            closing = tail.split("Closing date:")[-1].replace("View", "")

        # employer logo slug, e.g. /CRS  ->  CRS
        slug = ""
        logo = row.find("a", href=re.compile(r"sudanjob\.net/[A-Za-z]+$"))
        if logo:
            slug = logo["href"].rstrip("/").split("/")[-1]

        out.append(job("sudanjob", m.group(1), title, org, loc, closing,
                       f"https://sudanjob.net/jobview.php?id={m.group(1)}",
                       org_slug=slug))
    return out


# --------------------------------------------------------------------------
# ReliefWeb - official public API, no key, no scraping
# Flip enabled=True when ready.
# --------------------------------------------------------------------------
@source("reliefweb")
def reliefweb():
    """
    ReliefWeb API v2. NOTE: since 1 Nov 2025 the `appname` must be
    pre-approved by ReliefWeb - request one at https://reliefweb.int/help/api
    before enabling this source, otherwise requests are rejected.
    """
    r = requests.get(
        "https://api.reliefweb.int/v2/jobs",
        params={
            "appname": RELIEFWEB_APPNAME,
            "limit": 40,
            "sort[]": "date.created:desc",
            "filter[field]": "country.iso3",
            "filter[value]": "sdn",
            "fields[include][]": ["title", "source.name", "country.name",
                                  "city.name", "date.closing", "url"],
        },
        headers=UA, timeout=TIMEOUT,
    )
    r.raise_for_status()
    out = []
    for item in r.json().get("data", []):
        f = item["fields"]
        loc = ", ".join(c["name"] for c in f.get("city", [])) or \
              ", ".join(c["name"] for c in f.get("country", []))
        out.append(job(
            "reliefweb", item["id"], f.get("title", ""),
            (f.get("source") or [{}])[0].get("name", ""),
            loc, (f.get("date") or {}).get("closing", "")[:10],
            f.get("url", ""),
        ))
    return out


# --------------------------------------------------------------------------
# TEMPLATE: org career site on Greenhouse-style JSON
# Copy, rename, set enabled=True.
# --------------------------------------------------------------------------
@source("example_ats", enabled=False)
def example_ats():
    r = requests.get("https://boards-api.greenhouse.io/v1/boards/EXAMPLE/jobs",
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return [
        job("example_ats", p["id"], p["title"], "Example Org",
            (p.get("location") or {}).get("name", ""), "", p["absolute_url"])
        for p in r.json().get("jobs", [])
    ]


@source("manual")
def manual():
    import json
    import os
    if not os.path.exists("manual.json"):
        return []
    with open("manual.json", encoding="utf-8") as f:
        rows = json.load(f)
    out = []
    for r in rows:
        j = job("manual", r["id"], r["title"], r["org"],
                r.get("location", ""), r["closing"], r["url"],
                org_slug=r.get("org_slug", ""))
        j["title_ar"] = r.get("title_ar", "")
        j["org_ar"] = r.get("org_ar", "")
        j["location_ar"] = r.get("location_ar", "")
        out.append(j)
    return out


# --------------------------------------------------------------------------
# sudani.sd - WordPress + jobsearch plugin. Corporate careers page.
# No closing date published; only a post date. closing is left empty.
# --------------------------------------------------------------------------
@source("sudani")
def sudani():
    html = requests.get("https://sudani.sd/careers/", headers=UA,
                        timeout=TIMEOUT).text
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()

    for a in soup.find_all("a", href=re.compile(r"/job/[^/]+/?$")):
        href = a.get("href", "")
        m = re.search(r"/job/([^/?#]+)", href)
        if not m:
            continue
        slug = m.group(1)
        if slug in seen:
            continue

        title = (a.get("title") or a.get_text(" ", strip=True)).strip()
        if not title or len(title) < 3:
            continue
        seen.add(slug)

        # category link looks like /technology-jobs/ , /finance-jobs/
        cat = ""
        block = a.find_parent(["li", "div", "article"]) or a.parent
        if block:
            c = block.find("a", href=re.compile(r"/[a-z\-]+-jobs/?$"))
            if c:
                cat = c.get_text(" ", strip=True)

        j = job("sudani", slug, title, "Sudani",
                "Sudan", "",
                f"https://sudani.sd/job/{slug}/",
                org_slug="sudani")
        j["category"] = cat
        out.append(j)
    return out


# --------------------------------------------------------------------------
# sudancareer.com - WordPress. Titles are formatted:
#     "Senior Procurement Officer (Madani) - CRS"
# so org and location fall out of the title itself.
# Tries the WP REST API first, falls back to HTML.
# --------------------------------------------------------------------------
_SC_TITLE = re.compile(r"^(?P<title>.+?)\s*(?:\((?P<loc>[^)]*)\))?\s*[-–—]\s*(?P<org>[^-–—]+)$")
_SC_CLOSE = re.compile(
    r"(?:closing\s*date|apply\s*before|deadline|advertisement\s*end\s*date)\s*:?\s*"
    r"([0-9]{1,2}[/ -][A-Za-z0-9]{2,9}[/ -][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{1,2},?\s*[0-9]{4})",
    re.I)


def _sc_parse(title_raw, excerpt, url, ident):
    m = _SC_TITLE.match(title_raw.strip())
    if m:
        title = m.group("title").strip()
        org = m.group("org").strip()
        loc = (m.group("loc") or "").strip()
    else:
        title, org, loc = title_raw.strip(), "", ""
    if not loc:
        loc = "Sudan"
    cm = _SC_CLOSE.search(excerpt or "")
    closing = cm.group(1).strip() if cm else ""
    return job("sudancareer", ident, title, org, loc, closing, url)


@source("sudancareer")
def sudancareer():
    out = []
    # preferred: WordPress REST API
    try:
        r = requests.get("https://sudancareer.com/wp-json/wp/v2/posts",
                         params={"per_page": 30, "_fields": "id,link,title,excerpt"},
                         headers=UA, timeout=TIMEOUT)
        if r.status_code == 200:
            for post in r.json():
                t = re.sub(r"<[^>]+>", "", post["title"]["rendered"])
                e = re.sub(r"<[^>]+>", " ", post.get("excerpt", {}).get("rendered", ""))
                t = (t.replace("&#8211;", "-").replace("&amp;", "&")
                       .replace("&nbsp;", " ").replace("&#038;", "&"))
                j = _sc_parse(t, e, post["link"], post["id"])
                if j["org"]:
                    out.append(j)
            if out:
                return out
    except Exception:
        pass

    # fallback: HTML listing
    html = requests.get("https://sudancareer.com/", headers=UA, timeout=TIMEOUT).text
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    for h in soup.find_all(["h2", "h3"]):
        a = h.find("a", href=True)
        if not a or "/jobs/" in a["href"] or a["href"].rstrip("/").endswith(".com"):
            continue
        url = a["href"]
        if url in seen:
            continue
        seen.add(url)
        title_raw = a.get("title") or a.get_text(" ", strip=True)
        block = h.find_parent(["article", "div"])
        excerpt = block.get_text(" ", strip=True) if block else ""
        ident = url.rstrip("/").split("/")[-1]
        j = _sc_parse(title_raw, excerpt, url, ident)
        if j["org"]:
            out.append(j)
    return out


def collect():
    """Run every enabled source. One failure never kills the run."""
    all_jobs, errors = [], []
    for name, cfg in SOURCES.items():
        if not cfg["enabled"]:
            continue
        try:
            found = cfg["fn"]()
            print(f"  {name}: {len(found)} rows")
            all_jobs.extend(found)
        except Exception as e:
            print(f"  {name}: FAILED {type(e).__name__}: {e}")
            errors.append(name)
    return all_jobs, errors
        
