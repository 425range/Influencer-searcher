
from pathlib import Path
import shutil
import py_compile
import tempfile
import yaml

ROOT = Path.cwd()
HASHTAG = ROOT / "src" / "discovery" / "hashtag_recent.py"
CONFIG = ROOT / "config" / "campaign.yaml"
GUI = ROOT / "gui.py"
MAIN = ROOT / "main.py"

for p in (HASHTAG, CONFIG):
    if not p.exists():
        raise RuntimeError(f"Missing required file: {p}")

for p in (HASHTAG, CONFIG, GUI, MAIN):
    if p.exists():
        bak = p.with_suffix(p.suffix + ".official_hashtag.bak")
        if not bak.exists():
            shutil.copy2(p, bak)

module = '''from __future__ import annotations

from collections import defaultdict
from src.models import Candidate

OFFICIAL_ACTOR_ID = "apify/instagram-hashtag-scraper"


def _dataset_id(run):
    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        raise RuntimeError("Could not get Apify dataset id.")
    return dataset_id


def _clean_hashtags(values):
    return list(dict.fromkeys(
        str(x).strip().lstrip("#")
        for x in (values or [])
        if str(x).strip().lstrip("#")
    ))


def _username(item):
    return str(
        item.get("ownerUsername")
        or item.get("username")
        or item.get("owner")
        or item.get("authorUsername")
        or ""
    ).strip().lstrip("@")


def _source_hashtag(item):
    for key in ("query", "hashtag", "sourceHashtag", "searchQuery"):
        value = item.get(key)
        if value:
            return str(value).strip().lstrip("#")
    return ""


def _post_key(item):
    return str(
        item.get("id")
        or item.get("postId")
        or item.get("shortCode")
        or item.get("shortcode")
        or item.get("url")
        or ""
    )


def _run_official_actor(client, actor_id, hashtags, results_limit):
    run = client.actor(actor_id).call(
        run_input={
            "hashtags": hashtags,
            "resultsType": "posts",
            "resultsLimit": int(results_limit),
        }
    )
    if run is None:
        raise RuntimeError("Official Instagram Hashtag Scraper run failed.")
    return list(client.dataset(_dataset_id(run)).iterate_items())


def discover_by_hashtags(
    client,
    hashtags,
    actor_id=OFFICIAL_ACTOR_ID,
    initial_posts=100,
    max_posts=300,
    target_valid_candidates=10,
    min_followers=0,
    max_followers=10**12,
    expand_search=False,
    allow_unknown_followers=False,
):
    # Official hashtag results expose creator username, but follower count is
    # checked later by the existing Profile Scraper / hard-filter stage.
    del min_followers, max_followers, allow_unknown_followers

    hashtags = _clean_hashtags(hashtags)
    if not hashtags:
        return [], {}

    actor_id = actor_id or OFFICIAL_ACTOR_ID
    initial_posts = max(1, int(initial_posts))
    max_posts = max(initial_posts, int(max_posts))
    target_valid_candidates = max(1, int(target_valid_candidates))

    current_limit = initial_posts
    seen_posts = set()
    users = {}
    stats_by_tag = defaultdict(lambda: {"posts": 0, "authors": set()})
    actor_runs = 0

    while True:
        actor_runs += 1
        print(
            f"  hashtag run {actor_runs}: actor={actor_id}, "
            f"tags={len(hashtags)}, resultsLimit={current_limit}/tag, type=posts"
        )
        if actor_runs > 1:
            print(
                "  [cost warning] expansion re-runs the Actor with a larger "
                "resultsLimit; previous results may be returned again."
            )

        items = _run_official_actor(
            client=client,
            actor_id=actor_id,
            hashtags=hashtags,
            results_limit=current_limit,
        )

        for item in items:
            post_key = _post_key(item)
            if post_key and post_key in seen_posts:
                continue
            if post_key:
                seen_posts.add(post_key)

            username = _username(item)
            if not username:
                continue

            tag = _source_hashtag(item)
            tag_key = tag or "(unknown)"
            stats_by_tag[tag_key]["posts"] += 1
            stats_by_tag[tag_key]["authors"].add(username.lower())

            key = username.lower()
            if key not in users:
                users[key] = Candidate(
                    username=username,
                    profile_url=f"https://www.instagram.com/{username}/",
                    source="hashtag",
                    source_seed=f"#{tag}" if tag else "hashtag_search",
                    discovery_depth=0,
                    followers=None,
                )

        if not expand_search:
            print(
                f"  hashtag expansion OFF: discovered_unique_authors={len(users)}"
            )
            break

        if len(users) >= target_valid_candidates:
            print(
                f"  hashtag discovery stop: unique_authors={len(users)} "
                f">= target={target_valid_candidates}"
            )
            break

        if current_limit >= max_posts:
            print(
                f"  hashtag maximum reached: {current_limit}/tag, "
                f"unique_authors={len(users)}"
            )
            break

        current_limit = min(current_limit + initial_posts, max_posts)

    total_posts = 0
    all_authors = set()
    printable = {}

    for tag, st in sorted(stats_by_tag.items()):
        posts = st["posts"]
        authors = len(st["authors"])
        total_posts += posts
        all_authors |= st["authors"]
        printable[tag] = {
            "posts_seen": posts,
            "unique_authors": authors,
        }
        print(f"    #{tag}: posts={posts}, unique_authors={authors}")

    print(
        f"  hashtag summary: posts={total_posts}, "
        f"unique_authors={len(all_authors)}"
    )
    print(
        "  follower qualification will be measured after Profile Scraper "
        "and the normal follower hard filter."
    )

    return list(users.values()), {
        "actor_id": actor_id,
        "actor_runs": actor_runs,
        "results_limit_per_hashtag": current_limit,
        "posts_seen": total_posts,
        "unique_authors": len(all_authors),
        "by_hashtag": printable,
    }
'''

HASHTAG.write_text(module, encoding="utf-8")

cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
d = cfg.setdefault("discovery", {})
d["hashtag_actor_id"] = "apify/instagram-hashtag-scraper"
d.setdefault("use_hashtag_search", True)
d.setdefault("hashtag_initial_posts", 100)
d.setdefault("hashtag_max_posts", 300)
d["hashtag_expand_search"] = False
d.setdefault("hashtag_target_valid_candidates", 10)
CONFIG.write_text(
    yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
    encoding="utf-8",
)

for p in (GUI, MAIN):
    if p.exists():
        text = p.read_text(encoding="utf-8")
        text = text.replace(
            "instaprism/instagram-hashtag-posts",
            "apify/instagram-hashtag-scraper",
        )
        text = text.replace(
            "instaprism/instagram-hashtag-scraper",
            "apify/instagram-hashtag-scraper",
        )
        p.write_text(text, encoding="utf-8")

for p in (HASHTAG, GUI, MAIN):
    if p.exists() and p.suffix == ".py":
        cfile = Path(tempfile.gettempdir()) / (p.stem + "_official_hashtag.pyc")
        py_compile.compile(str(p), cfile=str(cfile), doraise=True)

print("[ok] switched hashtag Actor to apify/instagram-hashtag-scraper")
print("[ok] input = hashtags + resultsType=posts + resultsLimit")
print("[ok] default expansion = OFF")
print("[ok] follower filtering remains in Profile Scraper / hard-filter stage")
print("Next: python gui.py")
