import os

BASE_DIR = r"C:\XIIITradingSystems\Epoch_v3\14_aux_tools\social_media"

PLATFORMS = {
    "instagram": {
        "source_dir": os.path.join(BASE_DIR, "instagram", "source"),
        "output_dir": os.path.join(BASE_DIR, "instagram", "output"),
        "canvas_size": (1080, 1080),
        "formats": {
            "square": (1080, 1080),
            "portrait": (1080, 1350),
            "story": (1080, 1920),
            "landscape": (1080, 566),
        },
    },
    "twitter": {
        "source_dir": os.path.join(BASE_DIR, "twitter", "source"),
        "output_dir": os.path.join(BASE_DIR, "twitter", "output"),
        "canvas_size": (1200, 675),
        "formats": {
            "default": (1200, 675),
        },
    },
    "discord": {
        "source_dir": os.path.join(BASE_DIR, "discord", "source"),
        "output_dir": os.path.join(BASE_DIR, "discord", "output"),
        "canvas_size": (800, 600),
        "formats": {
            "default": (800, 600),
        },
    },
}

TEMPLATE_REGISTRY = {
    "instagram": [
        {
            "id": "two_50_50",
            "label": "Two - 50:50",
            "module": "templates.instagram.two_50_50",
            "required_images": 2,
        },
    ],
    "twitter": [],
    "discord": [],
}

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
