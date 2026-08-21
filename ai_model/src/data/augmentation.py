"""
augmentation.py
================
Training-set-only augmentation.

Hard rule enforced throughout this pipeline (see pipeline.py): augmentation
functions in this module are only ever called on the "train" split. val/test
are preprocessed but never augmented — augmenting them would make evaluation
metrics not reflect real deployment conditions.

Transforms are deliberately restricted to ones that are physically realistic
for smartphone photos of the eye conjunctiva under varying lighting/handling,
per the capture context Account 1 confirmed (handheld phone camera, EXIF
shows consumer Android device):
  - horizontal flip            (left/right eye symmetry — no clinical meaning
                                 is encoded in left-right orientation here)
  - small rotation (+/-10deg)  (hand tremor / imperfect device alignment)
  - brightness/contrast jitter (variable ambient lighting)
  - mild gaussian noise        (sensor noise, especially in low light)
  - mild gaussian blur         (focus/motion blur)

Deliberately EXCLUDED: vertical flip (anatomically implausible), heavy
color-channel shuffling or hue rotation (tissue color is a clinically
meaningful signal for anaemia screening — corrupting it works against the
task), cutout/erasing (could remove the exact conjunctiva region a mask-
derived ROI is meant to preserve).

Implemented with numpy/OpenCV only (no albumentations dependency) to keep
the pipeline's dependency surface minimal and auditable.
"""

import cv2
import numpy as np


def random_horizontal_flip(rgb_array, rng, p=0.5):
    if rng.random() < p:
        return np.ascontiguousarray(rgb_array[:, ::-1, :])
    return rgb_array


def random_rotation(rgb_array, rng, max_degrees=10):
    angle = rng.uniform(-max_degrees, max_degrees)
    h, w = rgb_array.shape[:2]
    center = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(rgb_array, matrix, (w, h), borderMode=cv2.BORDER_REFLECT_101)


def random_brightness_contrast(rgb_array, rng, brightness_range=0.2, contrast_range=0.2):
    brightness = 1.0 + rng.uniform(-brightness_range, brightness_range)
    contrast = 1.0 + rng.uniform(-contrast_range, contrast_range)
    x = rgb_array.astype(np.float32)
    mean = x.mean()
    x = (x - mean) * contrast + mean
    x = x * brightness
    return np.clip(x, 0, 255).astype(np.uint8)


def random_gaussian_noise(rgb_array, rng, sigma_range=(0, 6)):
    sigma = rng.uniform(*sigma_range)
    noise = rng.normal(0, sigma, size=rgb_array.shape)
    return np.clip(rgb_array.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def random_gaussian_blur(rgb_array, rng, p=0.3, max_kernel=3):
    if rng.random() < p:
        k = rng.choice([3, 5][:max_kernel // 2 + 1])
        return cv2.GaussianBlur(rgb_array, (k, k), 0)
    return rgb_array


def augment_train_image(rgb_array, seed=None):
    """
    Apply the full, ordered realistic augmentation stack to a single
    (H, W, 3) uint8 RGB array. `seed` should be derived per-image (e.g.
    hash of subject_id + epoch) by the caller for reproducible-but-varied
    augmentation across epochs; omit for fully random behavior.
    """
    rng = np.random.default_rng(seed)

    class _RNGAdapter:
        """Thin adapter so helpers above can share one numpy Generator."""
        def random(self_inner):
            return float(rng.random())

        def uniform(self_inner, low, high):
            return float(rng.uniform(low, high))

        def normal(self_inner, loc, scale, size):
            return rng.normal(loc, scale, size)

        def choice(self_inner, options):
            return int(rng.choice(options))

    r = _RNGAdapter()
    img = rgb_array
    img = random_horizontal_flip(img, r)
    img = random_rotation(img, r)
    img = random_brightness_contrast(img, r)
    img = random_gaussian_blur(img, r)
    img = random_gaussian_noise(img, r)
    return img
