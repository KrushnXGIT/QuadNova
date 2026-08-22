"""
Deterministic negative/positive test-image generators for the input-domain
firewall suite.

These are procedurally generated stand-ins for real-world negative photos
(rooms, hands, documents, food, objects, non-conjunctiva eye shots). The
project currently has NO real negative photo dataset — see
ai_model/validation/VALIDATION_DATASET.md for the documented gap and how to
add real negatives.

All generators are deterministic (fixed seeds) so tests are reproducible.
"""
from __future__ import annotations

import io
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def to_jpeg(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB").save(
        buf, format="JPEG", quality=92
    )
    return buf.getvalue()


def img_random_noise() -> bytes:
    rng = np.random.default_rng(1)
    return to_jpeg(rng.integers(0, 255, size=(480, 640, 3)).astype(np.uint8))


def img_room_scene() -> bytes:
    rng = np.random.default_rng(44)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([210, 205, 198])
    img[:, : w // 3] = np.array([180, 190, 200])
    img[h // 3: 2 * h // 3, w // 3: int(w * 0.75)] = np.array([235, 240, 245])
    img[int(h * 0.75):, :] = np.array([120, 85, 60])
    img = img + rng.normal(0, 4, (h, w, 3))
    return to_jpeg(img)


def img_object_on_table() -> bytes:
    """Blue mug on a desk — plain object photo."""
    rng = np.random.default_rng(7)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([190, 185, 178])
    img[int(h * 0.7):, :] = np.array([105, 80, 58])
    yy, xx = np.mgrid[0:h, 0:w]
    mug = (((xx - 480) / 110.0) ** 2 + ((yy - 380) / 130.0) ** 2) <= 1
    img[mug] = np.array([70, 90, 160])
    img += rng.normal(0, 4, (h, w, 3))
    return to_jpeg(img)


def img_hand() -> bytes:
    rng = np.random.default_rng(66)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([200, 200, 195])
    yy, xx = np.mgrid[0:h, 0:w]
    palm = (((xx - 480) / 190.0) ** 2 + ((yy - 400) / 260.0) ** 2) <= 1
    fingers = (((yy - 220) / 60.0) ** 2 + (((xx - 480) % 130 - 65) / 34.0) ** 2) <= 1
    skin = palm | fingers
    img[skin] = np.array([222, 170, 148])
    img += rng.normal(0, 4, (h, w, 3))
    return to_jpeg(img)


def img_document() -> bytes:
    rng = np.random.default_rng(55)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.uint8) * 245
    pil = Image.fromarray(img)
    d = ImageDraw.Draw(pil)
    y = 80
    while y < h - 60:
        d.line([100, y, 100 + int(rng.integers(300, 700)), y], fill=(40, 40, 45), width=6)
def img_food_plate() -> bytes:
    rng = np.random.default_rng(33)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([235, 232, 225])
    pil = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(pil)
    d.ellipse([280, 160, 680, 560], fill=(248, 246, 240))
    d.ellipse([360, 240, 520, 400], fill=(205, 60, 50))
    d.ellipse([385, 265, 495, 375], fill=(228, 120, 105))
    for i in range(8):
        ang = i * np.pi / 4
        cx, cy = 440 + 42 * np.cos(ang), 320 + 42 * np.sin(ang)
        d.ellipse([cx - 7, cy - 10, cx + 7, cy + 10], fill=(250, 230, 200))
    d.ellipse([540, 300, 640, 420], fill=(90, 140, 70))
    arr = np.asarray(pil).astype(np.float32) + rng.normal(0, 3, (h, w, 3))
    return to_jpeg(arr)


def img_normal_open_eye() -> bytes:
    """A NORMAL open eye — sclera + iris + pupil + pink canthus.

    NOT an everted conjunctiva capture. Guards the PHASE-4 requirement that
    generic eye appearance must not pass as conjunctiva.
    """
    rng = np.random.default_rng(88)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([225, 185, 165])
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = 480, 360
    sclera = (((xx - cx) / 220.0) ** 2 + ((yy - cy) / 100.0) ** 2) <= 1
    img[sclera] = np.array([235, 232, 225])
    iris = (((xx - (cx + 40)) / 55.0) ** 2 + ((yy - cy) / 55.0) ** 2) <= 1
    img[iris] = np.array([60, 40, 25])
    pupil = (((xx - (cx + 40)) / 22.0) ** 2 + ((yy - cy) / 22.0) ** 2) <= 1
    img[pupil] = np.array([10, 10, 10])
    canthus = (((xx - (cx - 205)) / 26.0) ** 2 + ((yy - cy) / 20.0) ** 2) <= 1
    img[canthus] = np.array([205, 95, 90])
    img += rng.normal(0, 3, (h, w, 3))
    return to_jpeg(img)


def img_lips_closeup() -> bytes:
    """Red/pink lips adjacent to the dark mouth line — non-eye red tissue."""
    rng = np.random.default_rng(99)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([225, 180, 165])
    yy, xx = np.mgrid[0:h, 0:w]
    lips = (((xx - 480) / 260.0) ** 2 + ((yy - 360) / 130.0) ** 2) <= 1
    img[lips] = np.array([195, 80, 90])
    gap = (((xx - 480) / 220.0) ** 2 + ((yy - 360) / 22.0) ** 2) <= 1
    img[gap] = np.array([35, 15, 15])
    img += rng.normal(0, 3, (h, w, 3))
    return to_jpeg(img)


def img_blurry_scene() -> bytes:
    rng = np.random.default_rng(77)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([215, 160, 155])
    img[:, w // 2:] = np.array([190, 120, 125])
    pil = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(radius=14)
    )
    arr = np.asarray(pil).astype(np.float32) + rng.normal(0, 2, (h, w, 3))
    return to_jpeg(arr)


def img_dark_scene() -> bytes:
    rng = np.random.default_rng(111)
    h, w = 720, 960
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([28, 24, 22])
    img += rng.normal(0, 2, (h, w, 3))
    return to_jpeg(img)


def img_weak_positive_room() -> bytes:
    """
    ADVERSARIAL: unrelated room photo with a small red/pink patch near a dark
    shadow — engineered to pass the chroma detector. This is the exact class
    of image that produced a fabricated Hb report before the firewall existed.
    """
    rng = np.random.default_rng(123)
    h, w = 900, 1200
    img = np.ones((h, w, 3), dtype=np.float32) * np.array([200, 197, 190])
    img[int(h * 0.7):, :] = np.array([90, 65, 45])
    yy, xx = np.mgrid[0:h, 0:w]
    patch = (((xx - 300) / 45.0) ** 2 + ((yy - 300) / 55.0) ** 2) <= 1
    img[patch] = np.array([205, 70, 75])
    shadow = (((xx - 300) / 70.0) ** 2 + ((yy - 380) / 40.0) ** 2) <= 1
    img[shadow] = np.array([25, 22, 20])
    img += rng.normal(0, 3, (h, w, 3))
    return to_jpeg(img)


NEGATIVE_GENERATORS: dict[str, Callable[[], bytes]] = {
    "random_noise": img_random_noise,
    "room_scene": img_room_scene,
    "object_photo": img_object_on_table,
    "hand": img_hand,
    "document": img_document,
    "food_plate": img_food_plate,
    "non_conjunctiva_eye": img_normal_open_eye,
    "lips_closeup": img_lips_closeup,
    "blurry_scene": img_blurry_scene,
    "dark_scene": img_dark_scene,
    "adversarial_weak_positive": img_weak_positive_room,
}


def build_full_frame_mask_png(h: int, w: int) -> bytes:
    """An arbitrary attacker-controlled mask covering the ENTIRE frame."""
    mask = np.zeros((h, w, 4), dtype=np.uint8)
    mask[:, :, :3] = 128
    mask[:, :, 3] = 255
    buf = io.BytesIO()
    Image.fromarray(mask, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()
