import os

from config import PLATFORMS, SUPPORTED_EXTENSIONS


def load_source_images() -> list[str]:
    """Scan Instagram source directory and return sorted image paths."""
    source_dir = PLATFORMS["instagram"]["source_dir"]
    if not os.path.isdir(source_dir):
        return []

    files = []
    for f in os.listdir(source_dir):
        ext = os.path.splitext(f)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            files.append(f)

    files.sort()
    return [os.path.join(source_dir, f) for f in files]
