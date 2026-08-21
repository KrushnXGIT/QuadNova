import torch
import numpy as np
import sys
sys.path.insert(0, '.')
from src.model.model import HbRegressor
from src.model.train import build_arrays, load_split
from src.data.labels import load_labels
from src.model.evaluate import regression_metrics

ck = torch.load('models/hb_regressor_best.pt', map_location='cpu', weights_only=False)
cfg = ck.get('config', {})
print('Config:', cfg)
labels = load_labels('data/metadata')
split_data = load_split('data/splits/split.json')
split = split_data.get('split', split_data)
arrays, rej = build_arrays('data/raw/verified_flat', split, labels, 'data/processed/model_cache')
model = HbRegressor(pretrained=cfg.get('pretrained', False))
model.load_state_dict(ck['model_state_dict'])
model.eval()
tm = cfg.get('target_mean', 0)
ts = cfg.get('target_std', 1)
for name, (imgs, tgts, ids) in arrays.items():
    preds = model(torch.from_numpy(imgs)).detach().numpy() * ts + tm
    m = regression_metrics(tgts, preds)
    print(f"{name}: MAE={m['MAE']:.4f} RMSE={m['RMSE']:.4f} R2={m['R2']:.4f} n={len(tgts)}")
baseline_pred = np.mean(arrays['train'][1])
print(f"Train mean: {baseline_pred:.4f}")
bm = regression_metrics(arrays['test'][1], np.full(len(arrays['test'][1]), baseline_pred))
print(f"Baseline MAE={bm['MAE']:.4f} RMSE={bm['RMSE']:.4f}")
