import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, str(Path("tests").resolve()))

from negative_images import NEGATIVE_GENERATORS
from app.services.ai_service import AIService

service = AIService()
service._ready = True


class Spy:
    def __init__(self):
        self.calls = []

    def predict_from_path(self, **kw):
        self.calls.append(kw)
        return {"success": True, "status": "PREDICTION_COMPLETE", "data": {}}


service._predictor = Spy()

for name, gen in NEGATIVE_GENERATORS.items():
    t0 = time.perf_counter()
    payload = gen()
    t1 = time.perf_counter()
    result = service.predict_upload(payload, ".jpg")
    t2 = time.perf_counter()
    print(f"{name:28s} gen={t1-t0:6.2f}s gate={t2-t1:7.2f}s status={result.get('status')}", flush=True)

print("ALL DONE", flush=True)
