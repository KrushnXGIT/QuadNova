"""
TEMPORARY DIAGNOSTIC PROBE — PHASE 1 evidence gathering.

Pushes procedurally generated "random / unrelated" images through the EXACT
production inference path (AIService.predict_upload with the real model) to
prove whether invalid inputs can receive an Hb value.

This file is diagnostic only and is removed after the fix is verified.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BACKEND_ROOT = Path(__file__).resolve().parent
AI_MODEL_ROOT = BACKEND_ROOT.parent / "ai_model"
for p in (str(BACKEND_ROOT), str(AI_MODEL_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.core.config import get_settings  # noqa: E402
from app.services.ai_service import AIService  # noqa: E402


def _jpeg(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB").save(
        buf, format="JPEG", quality=92
    )
    return buf.getvalue()


# ── Negative image generators (deterministic) ────────────────────────────
def img_red_object_on_table() -> bytes:
    """Red round object (apple-like) on a wooden table — classic false positive."""
    rng = np.random.default_rng(11)
    h, w = 720, 960
    wood = np.zeros((h, w, 3), dtype=np.float32)
    wood[..., 0] = 150 + 30 * np.sin(np.linspace(0, 60 * np.pi, w))[None, :]
    wood[..., 1] = 95 + 20 * np.sin(np.linspace(0, 45 * np.pi, w))[None, :]
    wood[..., 2] = 55 + 12 * np.sin(np.linspace(0, 30 * np.pi, w))[None, :]
    wood += rng.normal(0, 6, (h, w, 3))
    yy, xx = np.mgrid[0:h, 0:w]
    apple = ((yy - 380) ** 2 / 130 ** 2 + (xx - 480) ** 2 / 120 ** 2) <= 1
    shade = 1.0 - 0.35 * (((yy - 330) / 110.0).clip(0, 1))[..., None]
    wood[apple] = wood[apple] * 0 + np.array([200, 40, 45]) * shade[apple]
    return _jpeg(wood)


def img_skin_closeup() -> bytes:
    """Skin-textured close-up (cheek/hand-like) with soft shadows."""
    rng = np.random.default_rng(22)
    h, w = 720, 960
    base = np.array([225, 172, 150], dtype=np.float32)
    img = np.ones((h, w, 3), dtype=np.float32) * base
    # skin texture: low-frequency blotches + fine noise
    low = rng.normal(0, 1, (h // 8, w // 8, 1))
    low_range = float(low.max() - low.min())
    low = np.array(Image.fromarray(((low - low.min()) / (low_range + 1e-9) * 255).astype(np.uint8)[..., 0]).resize((w, h))).astype(np.float32)[..., None] / 255.0
    img += (low - 0.5) * 26
    img += rng.normal(0, 4, (h, w, 3))
    # soft shadow corner
    yy, xx = np.mgrid[0:h, 0:w]
    shadow = ((yy > h * 0.7) & (xx < w * 0.3)).astype(np.float32)
    img -= shadow[..., None] * 40
    return _jpeg(img)


def img_food_plate() -> bytes:
    """Plate with tomato slices and greens — red moist-looking regions."""
    rng = np.random.default_rng(33)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([235, 232, 225])
    d = ImageDraw.Draw(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)))
    d.ellipse([280, 160, 680, 560], fill=(248, 246, 240))          # plate
    d.ellipse([360, 240, 520, 400], fill=(205, 60, 50))            # tomato slice
    d.ellipse([385, 265, 495, 375], fill=(228, 120, 105))          # tomato flesh
    for i in range(8):                                             # seeds
        ang = i * np.pi / 4
        cx, cy = 440 + 42 * np.cos(ang), 320 + 42 * np.sin(ang)
        d.ellipse([cx - 7, cy - 10, cx + 7, cy + 10], fill=(250, 230, 200))
    d.ellipse([540, 300, 640, 420], fill=(90, 140, 70))            # greens
    arr = np.asarray(d._image if hasattr(d, "_image") else d.im).astype(np.float32)
    arr = arr + rng.normal(0, 3, arr.shape)
    return _jpeg(arr)


def img_room_scene() -> bytes:
    """Room-like scene: wall, window light, furniture rectangles."""
    rng = np.random.default_rng(44)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([210, 205, 198])
    img[:, : w // 3] = np.array([180, 190, 200])                   # wall section
    img[h // 3 : 2 * h // 3, w // 3 : int(w * 0.75)] = np.array([235, 240, 245])  # window
    img[int(h * 0.75):, :] = np.array([120, 85, 60])               # floor/furniture
    img = img + rng.normal(0, 4, (h, w, 3))
    return _jpeg(img)


def img_document() -> bytes:
    """White document with dark text lines."""
    rng = np.random.default_rng(55)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.uint8) * 245
    pil = Image.fromarray(img)
    d = ImageDraw.Draw(pil)
    y = 80
    while y < h - 60:
        d.line([100, y, 100 + int(rng.integers(300, 700)), y], fill=(40, 40, 45), width=6)
        y += int(rng.integers(28, 48))
    return _jpeg(np.asarray(pil).astype(np.float32))


def img_hand() -> bytes:
    """Hand/skin blob on neutral background."""
    rng = np.random.default_rng(66)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([200, 200, 195])
    yy, xx = np.mgrid[0:h, 0:w]
    palm = (((xx - 480) / 190.0) ** 2 + ((yy - 400) / 260.0) ** 2) <= 1
    fingers = (((yy - 220) / 60.0) ** 2 + (((xx - 480) % 130 - 65) / 34.0) ** 2) <= 1
    skin = palm | fingers
    img[skin] = np.array([222, 170, 148])
    img += rng.normal(0, 4, (h, w, 3))
    return _jpeg(img)


def img_blurry_pink() -> bytes:
    """Heavily blurred pinkish scene — tests blur gate interplay."""
    rng = np.random.default_rng(77)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([215, 160, 155])
    img[:, w // 2:] = np.array([190, 120, 125])
    pil = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(radius=14)
    )
    arr = np.asarray(pil).astype(np.float32) + rng.normal(0, 2, (h, w, 3))
    return _jpeg(arr)


def img_normal_open_eye() -> bytes:
    """
    A NORMAL open eye (NOT an everted inner eyelid / conjunctiva).
    Sclera (white), iris/pupil (dark), skin around, and a pinkish medial
    canthus (inner eye corner) — genuine anatomy that is red/pink AND
    has a dark neighbour (the pupil), which is exactly the heuristic the
    mask generator uses. This is the PHASE 4 danger case: eye-detected
    but NOT a valid conjunctiva capture.
    """
    rng = np.random.default_rng(88)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([225, 185, 165])  # skin
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = 480, 360
    sclera = (((xx - cx) / 220.0) ** 2 + ((yy - cy) / 100.0) ** 2) <= 1
    img[sclera] = np.array([235, 232, 225])
    iris = (((xx - (cx + 40)) / 55.0) ** 2 + ((yy - cy) / 55.0) ** 2) <= 1
    img[iris] = np.array([60, 40, 25])
    pupil = (((xx - (cx + 40)) / 22.0) ** 2 + ((yy - cy) / 22.0) ** 2) <= 1
    img[pupil] = np.array([10, 10, 10])
    # medial canthus (inner eye corner) — genuinely pinkish tissue, right
    # next to the dark iris/pupil.
    canthus = (((xx - (cx - 205)) / 26.0) ** 2 + ((yy - cy) / 20.0) ** 2) <= 1
    img[canthus] = np.array([205, 95, 90])
    img += rng.normal(0, 3, (h, w, 3))
    return _jpeg(img)


def img_lips_closeup() -> bytes:
    """
    Close-up of lips/mouth: red/pink lip tissue directly adjacent to the
    dark oral cavity gap between the lips — satisfies both the redness
    heuristic and the "nearby dark context" heuristic without being an
    eye at all.
    """
    rng = np.random.default_rng(99)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([225, 180, 165])  # skin
    yy, xx = np.mgrid[0:h, 0:w]
    lips = (((xx - 480) / 260.0) ** 2 + ((yy - 360) / 130.0) ** 2) <= 1
    img[lips] = np.array([195, 80, 90])
    gap = (((xx - 480) / 220.0) ** 2 + ((yy - 360) / 22.0) ** 2) <= 1
    img[gap] = np.array([35, 15, 15])
    img += rng.normal(0, 3, (h, w, 3))
    return _jpeg(img)


NEGATIVES = {
    "red_object": img_red_object_on_table,
    "skin_closeup": img_skin_closeup,
    "food_plate": img_food_plate,
    "room_scene": img_room_scene,
    "document": img_document,
    "hand": img_hand,
    "blurry_pink": img_blurry_pink,
    "normal_open_eye": img_normal_open_eye,
    "lips_closeup": img_lips_closeup,
}


def main() -> None:
    settings = get_settings()
    print(f"AUTO_MASK_ENABLED={settings.AUTO_MASK_ENABLED}")
    service = AIService()
    ready = service.initialize()
    print(f"model_ready={ready}")
    if not ready:
        print("FATAL: model not ready; cannot probe live path")
        sys.exit(2)

    print("-" * 78)
    leaked = 0
    for name, gen in NEGATIVES.items():
        payload = gen()
        result = service.predict_upload(payload, ".jpg")
        status = result.get("status")
        success = result.get("success")
        hb = (result.get("data") or {}).get("estimated_hb_g_dl")
        err_code = (result.get("error") or {}).get("code")
        marker = "LEAK!!!" if (success and hb is not None) else "rejected"
        if success and hb is not None:
            leaked += 1
        print(
            f"{name:14s} -> status={status:22s} success={success} "
            f"hb={hb} error={err_code} [{marker}]"
        )
    print("-" * 78)
    print(f"RESULT: {leaked}/{len(NEGATIVES)} negative images RECEIVED AN Hb VALUE")


if __name__ == "__main__":
    main()