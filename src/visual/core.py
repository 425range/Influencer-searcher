from io import BytesIO
import requests
import torch
import torch.nn.functional as F
from PIL import Image
from transformers import AutoModel, AutoProcessor

IMAGE_FIELDS = ("displayUrl","imageUrl","thumbnailUrl","displayURL","thumbnailSrc")

def extract_image_urls(profile_item, limit=6):
    """
    Return ONE representative image per Instagram post.

    Important:
    - A carousel/sidecar post counts as ONE post.
    - We use only the post-level display/thumbnail image.
    - We DO NOT expand childPosts / sidecarChildren / children.
    - Therefore limit=6 means up to 6 different posts, not 6 images
      from one carousel.
    """
    urls = []

    for post in profile_item.get("latestPosts") or []:
        if not isinstance(post, dict):
            continue

        representative_url = None

        # Prefer the post's own cover/display image.
        for field in IMAGE_FIELDS:
            value = post.get(field)
            if isinstance(value, str) and value.startswith("http"):
                representative_url = value
                break

        # Very conservative fallback:
        # only if the post itself has no image URL, use the FIRST child.
        if representative_url is None:
            for child_key in ("childPosts", "sidecarChildren", "children"):
                children = post.get(child_key) or []
                if not isinstance(children, list) or not children:
                    continue

                first_child = children[0]
                if not isinstance(first_child, dict):
                    continue

                for field in IMAGE_FIELDS:
                    value = first_child.get(field)
                    if isinstance(value, str) and value.startswith("http"):
                        representative_url = value
                        break

                if representative_url:
                    break

        if representative_url and representative_url not in urls:
            urls.append(representative_url)

        if len(urls) >= limit:
            break

    return urls[:limit]

def load_image(url, timeout=15):
    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent":"Mozilla/5.0"}
        )
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception as e:
        print(f"[image error] {url}: {e}")
        return None

class SigLIP2Encoder:
    def __init__(self, model_name="google/siglip2-base-patch16-224", batch_size=8):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = batch_size
        print(f"[SigLIP2] device={self.device}")
        print(f"[SigLIP2] model={model_name}")
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device).eval()

    @torch.no_grad()
    def encode_images(self, images):
        chunks = []
        for start in range(0, len(images), self.batch_size):
            batch = images[start:start+self.batch_size]
            inputs = self.processor(images=batch, return_tensors="pt")
            inputs = {k:v.to(self.device) for k,v in inputs.items()}
            features = self.model.get_image_features(**inputs)
            if not torch.is_tensor(features):
                features = getattr(features, "pooler_output", features[0])
            chunks.append(F.normalize(features, p=2, dim=-1).cpu())
        return torch.cat(chunks, dim=0)

def account_embedding(encoder, images):
    if not images:
        return None
    emb = encoder.encode_images(images)
    if emb.numel() == 0:
        return None
    return F.normalize(emb.mean(dim=0, keepdim=True), p=2, dim=-1)

def seed_embedding(embeddings):
    usable = [e for e in embeddings if e is not None]
    if not usable:
        return None
    return F.normalize(torch.cat(usable, dim=0).mean(dim=0, keepdim=True), p=2, dim=-1)

def cosine_similarity(a, b):
    if a is None or b is None:
        return None
    return float(F.cosine_similarity(a, b, dim=-1).item())
