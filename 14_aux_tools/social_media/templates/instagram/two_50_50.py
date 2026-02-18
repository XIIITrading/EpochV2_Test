from PIL import Image


def render(
    image_paths: list[str],
    canvas_size: tuple[int, int],
    bg_color: str,
    fit_mode: str = "cover",
) -> Image.Image:
    """Two - 50:50 vertical stack template.

    Takes exactly 2 images, stacks them vertically. Top image = file prefixed 1_,
    bottom image = file prefixed 2_. Each image occupies exactly 50% of the canvas
    height.

    Fit modes:
        cover   – scale to fill slot, center-crop overflow (no background visible)
        contain – scale entire image to fit inside slot (no cropping), center
                  on both axes, background color fills any leftover space

    Args:
        image_paths: sorted list [top_image_path, bottom_image_path]
        canvas_size: (width, height) tuple from platform config
        bg_color: hex string e.g. '#0D0D0D'
        fit_mode: "cover" or "contain"

    Returns:
        PIL Image ready to save
    """
    canvas_w, canvas_h = canvas_size
    slot_h = canvas_h // 2

    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_color)

    for i, path in enumerate(image_paths):
        img = Image.open(path).convert("RGB")
        y_offset = 0 if i == 0 else slot_h

        if fit_mode in ("fit_height", "contain"):
            scaled = _contain(img, canvas_w, slot_h)
            x_offset = (canvas_w - scaled.width) // 2
            y_pad = (slot_h - scaled.height) // 2
            canvas.paste(scaled, (x_offset, y_offset + y_pad))
        else:
            slot = _cover_crop(img, canvas_w, slot_h)
            canvas.paste(slot, (0, y_offset))

    return canvas


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Scale image to cover target dimensions, then center-crop to exact size."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _contain(img: Image.Image, slot_w: int, slot_h: int) -> Image.Image:
    """Scale entire image to fit inside the slot — no cropping.

    Uses min(scale_w, scale_h) so the full image is always visible.
    The caller centers the result and fills leftover space with bg color.
    """
    src_w, src_h = img.size
    scale = min(slot_w / src_w, slot_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)

    return img.resize((new_w, new_h), Image.LANCZOS)
