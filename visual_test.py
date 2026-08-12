import argparse
from pathlib import Path
import pandas as pd, torch, yaml
from src.visual.core import load_image, SigLIP2Encoder, account_embedding, seed_embedding, cosine_similarity

def load_cfg(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def urls_from_row(row, n):
    urls = []
    for i in range(1, n+1):
        col = f"image_{i}"
        if col in row.index and not pd.isna(row[col]):
            value = str(row[col]).strip()
            if value.startswith("http"):
                urls.append(value)
    return urls

def main(config):
    cfg = load_cfg(config)
    src = Path(cfg["output"]["candidates_with_images"])
    df = pd.read_excel(src)
    user_col = cfg["input"]["username_column"]
    seed_users = {x.strip().lstrip("@").lower() for x in cfg["seeds"]["usernames"]}
    n = int(cfg["images"]["images_per_account"])
    timeout = int(cfg["images"]["request_timeout_seconds"])

    encoder = SigLIP2Encoder(
        cfg["siglip"]["model_name"],
        int(cfg["siglip"]["batch_size"]),
    )

    cache_path = Path(cfg["output"]["embeddings_cache"])
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = torch.load(cache_path, map_location="cpu", weights_only=False) if cache_path.exists() else {}
    embeddings, used = {}, {}

    for idx, row in df.iterrows():
        username = str(row[user_col]).strip().lstrip("@")
        key = username.lower()
        if key in cache:
            embeddings[key] = cache[key]
            used[key] = "cache"
            print(f"{idx+1}/{len(df)} {username}: cache")
            continue

        images = []
        for url in urls_from_row(row, n):
            img = load_image(url, timeout)
            if img is not None:
                images.append(img)

        emb = account_embedding(encoder, images)
        if emb is None:
            print(f"{idx+1}/{len(df)} {username}: no usable images")
            used[key] = 0
            continue

        embeddings[key] = emb
        used[key] = len(images)
        cache[key] = emb
        torch.save(cache, cache_path)
        print(f"{idx+1}/{len(df)} {username}: {len(images)} images")

    ref = seed_embedding([embeddings[k] for k in seed_users if k in embeddings])
    if ref is None:
        raise RuntimeError("No usable seed embeddings")

    rows = []
    for _, row in df.iterrows():
        username = str(row[user_col]).strip().lstrip("@")
        key = username.lower()
        if key in seed_users:
            continue
        result = row.to_dict()
        result["visual_similarity"] = cosine_similarity(ref, embeddings.get(key))
        result["images_used_for_embedding"] = used.get(key, 0)
        rows.append(result)

    out = pd.DataFrame(rows).sort_values(
        "visual_similarity",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)
    out.insert(0, "visual_rank", range(1, len(out)+1))

    path = Path(cfg["output"]["visual_results"])
    out.to_excel(path, index=False)
    print(out[[c for c in ["visual_rank",user_col,"followers","visual_similarity","images_used_for_embedding"] if c in out.columns]].head(20).to_string(index=False))
    print(f"Saved: {path}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/visual.yaml")
    main(p.parse_args().config)
