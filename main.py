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

KEEP = 1500  # how many historical keys/fingerprints to retain


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)


def caption(j):
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
    lines += [
        "",
        f"رابط التقديم:\n{j['url']}",
        "",
        _tags(j),
    ]
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
    os.remove(img_path)

    if r.status_code != 200:
        print(f"  FB ERROR {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return False
    print(f"  posted photo -> {r.json().get('post_id') or r.json().get('id')}")
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


def main():
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
            except Exception as e:
                print(f"  render failed: {e}", file=sys.stderr)
            ok = True
        else:
            ok = publish(j, n)
        if ok:
            sent += 1
            keys.add(j["key"])
            fps.add(j["fp"])

    state["keys"] = sorted(keys)[-KEEP:]
    state["fps"] = sorted(fps)[-KEEP:]
    save_state(state)

    print(f"\ndone. dry_run={DRY_RUN} posted={sent} "
          f"queued={len(new) - len(batch)} failed_sources={errors}")


if __name__ == "__main__":
    main()
        
