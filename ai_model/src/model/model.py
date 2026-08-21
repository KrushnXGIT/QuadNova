"""Lightweight transfer-learning regression architecture."""

import torch
from torch import nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small


class HbRegressor(nn.Module):
    """MobileNetV3-small feature extractor with a continuous Hb head."""

    def __init__(self, pretrained=False, freeze_backbone=False):
        super().__init__()
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        backbone = mobilenet_v3_small(weights=weights)
        self.features = backbone.features
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.regression_head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(576, 128),
            nn.Hardswish(),
            nn.Dropout(0.2),
            nn.Linear(128, 1),
        )
        if freeze_backbone:
            for parameter in self.features.parameters():
                parameter.requires_grad = False

    def forward(self, images):
        features = self.pool(self.features(images))
        return self.regression_head(features).squeeze(1)
