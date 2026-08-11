from pathlib import Path
import yaml


def load_config(path: str) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
