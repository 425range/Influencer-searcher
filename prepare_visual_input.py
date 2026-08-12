import argparse, os
from pathlib import Path
import pandas as pd, yaml
from apify_client import ApifyClient
from dotenv import load_dotenv
from src.visual.core import extract_image_urls

def load_cfg(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def dataset_id(run):
    x = getattr(run, "default_dataset_id", None)
    if not x and isinstance(run, dict):
        x = run.get("defaultDatasetId")
    if not x:
        raise RuntimeError("Apify dataset id not found")
    return x

def main(config):
    load_dotenv()
    cfg = load_cfg(config)
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN missing from .env")

    src = Path(cfg["input"]["candidates_excel"])
    df = pd.read_excel(src)
    user_col = cfg["input"]["username_column"]
    seeds = [x.strip().lstrip("@") for x in cfg["seeds"]["usernames"]]
    users = [str(x).strip().lstrip("@") for x in df[user_col].dropna()]
    all_users = list(dict.fromkeys(users + seeds))

    client = ApifyClient(token)
    run = client.actor(cfg["apify"]["actor_id"]).call(
        run_input={"usernames": all_users}
    )
    items = list(client.dataset(dataset_id(run)).iterate_items())
    by_user = {str(x.get("username","")).lower():x for x in items if x.get("username")}

    n = int(cfg["images"]["images_per_account"])
    rows = []
    seed_set = {x.lower() for x in seeds}

    for _, r in df.iterrows():
        username = str(r[user_col]).strip().lstrip("@")
        row = r.to_dict()
        row["is_seed"] = username.lower() in seed_set
        urls = extract_image_urls(by_user.get(username.lower(), {}), n)
        row["images_found"] = len(urls)
        for i in range(n):
            row[f"image_{i+1}"] = urls[i] if i < len(urls) else ""
        rows.append(row)

    existing = {str(x).strip().lstrip("@").lower() for x in df[user_col].dropna()}
    for username in seeds:
        if username.lower() in existing:
            continue
        urls = extract_image_urls(by_user.get(username.lower(), {}), n)
        row = {
            user_col: username,
            "profile_url": f"https://www.instagram.com/{username}/",
            "is_seed": True,
            "images_found": len(urls),
        }
        for i in range(n):
            row[f"image_{i+1}"] = urls[i] if i < len(urls) else ""
        rows.append(row)

    out = pd.DataFrame(rows)
    path = Path(cfg["output"]["candidates_with_images"])
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_excel(path, index=False)
    print(out[[user_col,"is_seed","images_found"]].to_string(index=False))
    print(f"Saved: {path}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/visual.yaml")
    main(p.parse_args().config)
