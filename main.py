#!/usr/bin/env python3
"""
Runner. Collects from every enabled source, dedups, posts to a Facebook Page.
Dry-run by default. Set DRY_RUN=false to publish.

Translation and image rendering plug in at the marked point - they operate on
the normalized record, so they work for every source without modification.
"""
import json
import os
import sys
import time

import requests

import sources
import render
import translate

STATE_FILE = "state.json"
GRAPH = "https://graph.facebook.com/v25.0"

DRY_RUN = os.getenv("DRY_RUN", "true").lower() != "false"
PAGE_ID = os.getenv("FB_PAGE_ID", "")
PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN", "")
MAX_PER_RUN = int(os.getenv("MAX_PER_RUN", "4"))
SPACING_MIN = int(os.getenv("SPACING_MIN", "40"))

# Telegram is optional - leave the secrets unset and it is skipped silently.
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TG_CHAT_ID", "")

KEEP = 1500

DIGEST = os.getenv("DIGEST", "").lower() == "true"
DIGEST_MAX = int(os.getenv("DIGEST_MAX", "14"))     # rows printed on the card
DIGEST_LINKS = int(os.getenv("DIGEST_LINKS", "24")) # links posted as comments

# scheduled posts cannot be commented on until they go live, so their ids are
# parked here and retried on later runs
PENDING = []  # how many historical keys/fingerprints to retain


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)


def caption(j, inline_link=False):
    translate.enrich(j)
    title = j.get("title_ar") or j["title"]
    org = j.get("org_ar") or j["org"]
    loc = j.get("location_ar") or j["location"]
    closing = j.get("closing_ar") or j["closing"]
    lines = [
        f"فرصة عمل | {org}",
        "",
        f"الوظيفة: {title}",
    ]
    # keep the English title too - applicants search for it
    if j.get("title_ar") and j["title_ar"] != j["title"]:
        lines.append(f"({j['title']})")
    if loc:
        lines.append(f"الموقع: {loc}")
    if closing:
        lines.append(f"آخر موعد للتقديم: {closing}")
    if inline_link:
        lines += ["", f"رابط التقديم:\n{j['url']}"]
    else:
        lines += ["", "رابط التقديم في أول تعليق 👇"]
    lines += ["", _tags(j)]
    return "\n".join(lines)


UN_ORGS = ("unhcr", "unicef", "undp", "unfpa", "unops", "wfp", "who", "fao",
           "iom", "unido", "unesco", "ocha", "united nations")


def _tags(j):
    tags = ["#وظائف_السودان", "#وظائف_شاغرة"]
    org = j.get("org", "").lower()
    if any(u in org for u in UN_ORGS):
        tags.append("#الأمم_المتحدة")
    elif j.get("source") == "sudani":
        tags.append("#سوداني")
    return " ".join(tags)


def telegram(j, img_path):
    """Post the same card + caption to a Telegram channel. Best effort:
    a Telegram failure never affects the Facebook post."""
    if not (TG_TOKEN and TG_CHAT):
        return None
    try:
        cap = caption(j, inline_link=True)
        if len(cap) > 1024:                 # Telegram photo caption limit
            cap = cap[:1020].rsplit("\n", 1)[0] + "\n…"
        with open(img_path, "rb") as fh:
            r = requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                data={"chat_id": TG_CHAT, "caption": cap},
                files={"photo": fh}, timeout=45)
        if r.status_code == 200:
            print("  telegram ok")
            return True
        print(f"  TELEGRAM ERROR {r.status_code}: {r.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"  TELEGRAM ERROR {type(e).__name__}: {e}", file=sys.stderr)
    return False


def comment_link(post_id, j):
    """Put the apply link in the first comment. Facebook suppresses reach on
    posts carrying an external link in the body, so the link lives here."""
    body = {
        "message": f"رابط التقديم:\n{j['url']}",
        "access_token": PAGE_TOKEN,
    }
    r = requests.post(f"{GRAPH}/{post_id}/comments", data=body, timeout=30)
    if r.status_code != 200:
        print(f"  COMMENT ERROR {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return False
    print("  link comment ok")
    return True


def publish(j, n):
    img_path = f"card_{j['key'].replace(':', '_')}.png"
    try:
        render.build_card(j, img_path)
    except Exception as e:
        print(f"  render failed ({e}) - falling back to link post", file=sys.stderr)
        return _publish_link(j, n)

    body = {"caption": caption(j), "access_token": PAGE_TOKEN}
    if n > 0:
        body["published"] = "false"
        body["scheduled_publish_time"] = int(time.time()) + n * SPACING_MIN * 60

    with open(img_path, "rb") as fh:
        r = requests.post(f"{GRAPH}/{PAGE_ID}/photos", data=body,
                          files={"source": fh}, timeout=60)

    telegram(j, img_path)
    os.remove(img_path)

    if r.status_code != 200:
        print(f"  FB ERROR {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return False

    data = r.json()
    post_id = data.get("post_id") or data.get("id")
    print(f"  posted photo -> {post_id}")

    # scheduled posts have no comments endpoint until they go live
    if post_id:
        if n == 0:
            comment_link(post_id, j)
        else:
            PENDING.append({"post_id": post_id, "url": j["url"]})
    return True


def _publish_link(j, n):
    body = {"message": caption(j), "link": j["url"], "access_token": PAGE_TOKEN}
    if n > 0:
        body["published"] = "false"
        body["scheduled_publish_time"] = int(time.time()) + n * SPACING_MIN * 60
    r = requests.post(f"{GRAPH}/{PAGE_ID}/feed", data=body, timeout=30)
    if r.status_code != 200:
        print(f"  FB ERROR {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return False
    print(f"  posted link -> {r.json().get('id')}")
    return True


def flush_pending(state):
    """Try to add the link comment to posts scheduled on earlier runs."""
    still = []
    for p in state.get("pending", []):
        body = {"message": f"رابط التقديم:\n{p['url']}", "access_token": PAGE_TOKEN}
        try:
            r = requests.post(f"{GRAPH}/{p['post_id']}/comments",
                              data=body, timeout=30)
            if r.status_code == 200:
                print(f"  pending comment ok -> {p['post_id']}")
                continue
            # not live yet - keep for the next run
            still.append(p)
        except Exception:
            still.append(p)
    state["pending"] = still[-60:]


def run_digest():
    """One post listing every open vacancy. Runs twice a week."""
    from datetime import date

    jobs, errors = sources.collect()

    open_jobs, seen = [], set()
    for j in jobs:
        if not sources.valid(j):
            continue
        if j["fp"] in seen:
            continue
        seen.add(j["fp"])
        dt = sources.parse_closing(j["closing"]) if j["closing"] else None
        translate.enrich(j)
        # undated jobs sort last
        j["_dt"] = dt or date(2099, 1, 1)
        open_jobs.append(j)

    open_jobs.sort(key=lambda x: x["_dt"])
    total = len(open_jobs)
    print(f"{total} open vacancies")
    if total < 4:
        print("not enough for a digest - skipping")
        return

    shown = open_jobs[:DIGEST_MAX]
    img = "digest.png"
    render.build_digest(shown, img, total=total)

    lines = [f"{total} فرصة عمل متاحة الآن", ""]
    for j in shown:
        org = j.get("org_ar") or j["org"]
        close = j.get("closing_ar") or j["closing"]
        line = f"• {j.get('title_ar') or j['title']} — {org}"
        if close:
            line += f" (حتى {close})"
        lines.append(line)
    if total > len(shown):
        lines += ["", f"و{total - len(shown)} فرصة أخرى — الروابط في التعليقات"]
    lines += ["", "الروابط في التعليقات 👇", "",
              "#وظائف_السودان #وظائف_شاغرة"]
    cap = "\n".join(lines)

    if DRY_RUN:
        print("--- dry run ---")
        print(cap[:1200])
        print(f"  card -> {img}  ({len(shown)} shown of {total})")
        return

    with open(img, "rb") as fh:
        r = requests.post(f"{GRAPH}/{PAGE_ID}/photos",
                          data={"caption": cap[:1900], "access_token": PAGE_TOKEN},
                          files={"source": fh}, timeout=60)
    if r.status_code != 200:
        print(f"  FB ERROR {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return
    post_id = r.json().get("post_id") or r.json().get("id")
    print(f"  digest posted -> {post_id}")

    # every link, including the ones not on the card, chunked into comments
    chunk = []
    for j in open_jobs[:DIGEST_LINKS]:
        chunk.append(f"{j.get('title_ar') or j['title']}\n{j['url']}")
        if len(chunk) == 4:
            _digest_comment(post_id, chunk)
            chunk = []
    if chunk:
        _digest_comment(post_id, chunk)

    if TG_TOKEN and TG_CHAT:
        try:
            with open(img, "rb") as fh:
                requests.post(
                    f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                    data={"chat_id": TG_CHAT, "caption": cap[:1020]},
                    files={"photo": fh}, timeout=45)
            print("  telegram digest ok")
        except Exception as e:
            print(f"  TELEGRAM ERROR: {e}", file=sys.stderr)


def _digest_comment(post_id, items):
    body = {"message": "\n\n".join(items), "access_token": PAGE_TOKEN}
    r = requests.post(f"{GRAPH}/{post_id}/comments", data=body, timeout=30)
    if r.status_code != 200:
        print(f"  COMMENT ERROR {r.status_code}: {r.text[:200]}", file=sys.stderr)
    else:
        print(f"  links comment ok ({len(items)})")


def main():
    if DIGEST:
        run_digest()
        return

    print("collecting...")
    jobs, errors = sources.collect()
    if not jobs and errors:
        print("every source failed")
        sys.exit(1)

    state = load_state()
    if state is None:
        save_state({
            "keys": sorted({j["key"] for j in jobs}),
            "fps": sorted({j["fp"] for j in jobs}),
        })
        print(f"seeded with {len(jobs)} existing jobs - no posts on first run")
        return

    keys = set(state.get("keys", []))
    fps = set(state.get("fps", []))

    new, seen_fp = [], set()
    for j in jobs:
        if j["key"] in keys or j["fp"] in fps or j["fp"] in seen_fp:
            continue          # already posted, or same vacancy from another site
        if not sources.valid(j):
            print(f"  SKIP incomplete {j['key']} {j['title'][:40]!r}")
            keys.add(j["key"])
            continue
        seen_fp.add(j["fp"])
        new.append(j)

    print(f"{len(new)} new after dedup")
    batch = new[:MAX_PER_RUN]
    sent = 0

    for n, j in enumerate(batch):
        print(f"\n[{j['key']}] {j['org']} / {j['title']}")
        if DRY_RUN:
            print("--- dry run ---")
            print(caption(j))
            try:
                p = render.build_card(j, f"dryrun_{j['key'].replace(':', '_')}.png")
                print(f"  card -> {p}")
                if TG_TOKEN and TG_CHAT:
                    print("  telegram: would post (dry run)")
            except Exception as e:
                print(f"  render failed: {e}", file=sys.stderr)
            ok = True
        else:
            ok = publish(j, n)
        if ok:
            sent += 1
            keys.add(j["key"])
            fps.add(j["fp"])

    if not DRY_RUN and PAGE_TOKEN:
        flush_pending(state)
    state["pending"] = state.get("pending", []) + PENDING
    state["keys"] = sorted(keys)[-KEEP:]
    state["fps"] = sorted(fps)[-KEEP:]
    save_state(state)

    print(f"\ndone. dry_run={DRY_RUN} posted={sent} "
          f"queued={len(new) - len(batch)} failed_sources={errors}")


if __name__ == "__main__":
    main()
