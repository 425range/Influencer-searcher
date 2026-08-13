import torch
from src.visual.core import extract_image_urls, load_image, SigLIP2Encoder, account_embedding, seed_embedding, cosine_similarity


def rank_candidates_visual(candidates, item_by_username, seed_usernames, cfg):
    model_name = cfg.get("model_name", "google/siglip2-base-patch16-224")
    batch_size = int(cfg.get("batch_size", 8))
    images_per_account = int(cfg.get("images_per_account", 6))
    timeout = int(cfg.get("request_timeout_seconds", 15))

    encoder = SigLIP2Encoder(model_name=model_name, batch_size=batch_size)
    embeddings = {}

    usernames = list(dict.fromkeys([c.username for c in candidates] + list(seed_usernames)))
    for idx, username in enumerate(usernames, start=1):
        item = item_by_username.get(username.lower(), {})
        urls = extract_image_urls(item, images_per_account)
        images = []
        for url in urls:
            img = load_image(url, timeout)
            if img is not None:
                images.append(img)
        emb = account_embedding(encoder, images)
        if emb is not None:
            embeddings[username.lower()] = emb
        print(f"  visual {idx}/{len(usernames)} {username}: {len(images)} images")

    seed_vectors = [embeddings[s.lower()] for s in seed_usernames if s.lower() in embeddings]
    reference = seed_embedding(seed_vectors)
    if reference is None:
        raise RuntimeError("Could not build seed visual embedding. Check seed images.")

    for c in candidates:
        emb = embeddings.get(c.username.lower())
        c.visual_similarity = cosine_similarity(reference, emb) if emb is not None else None

    ranked = sorted(
        candidates,
        key=lambda c: (c.visual_similarity is not None, c.visual_similarity or -1),
        reverse=True,
    )
    for rank, c in enumerate(ranked, start=1):
        c.visual_rank = rank
    return ranked
