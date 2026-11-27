"""Generate deterministic tenant routing quality evidence.

This report intentionally uses the same classifier node as production and no
LLM, vector database, or external service. It is suitable for CI and local
acceptance evidence.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("TENANT_STORAGE_MODE", "memory")

from tenant_agent import classify_agent  # noqa: E402


CASES = [
    {"id": "maintenance-leak", "text": "Phòng tắm bị rò nước cần sửa", "intent": "maintenance", "urgency": "high"},
    {"id": "payment-receipt", "text": "Tôi cần biên lai thanh toán tiền thuê", "intent": "payment", "urgency": "low"},
    {"id": "lease-renewal", "text": "Tôi muốn hỏi thủ tục gia hạn hợp đồng", "intent": "lease", "urgency": "low"},
    {"id": "noise-neighbor", "text": "Hàng xóm mở nhạc tiếng ồn cả đêm", "intent": "noise", "urgency": "medium"},
    {"id": "utility-outage", "text": "Căn hộ bị mất nước từ sáng", "intent": "utilities", "urgency": "high"},
    {"id": "security-lock", "text": "Không khóa được cửa căn hộ, cần hỗ trợ khẩn cấp", "intent": "security", "urgency": "high"},
    {"id": "move-out", "text": "Tôi muốn hỏi thủ tục trả nhà và hoàn cọc", "intent": "move_in_out", "urgency": "low"},
    {"id": "fire-critical", "text": "Có khói và mùi khét trong căn hộ", "intent": "general", "urgency": "critical"},
    {"id": "flood-critical", "text": "Ống nước bị vỡ, căn hộ đang ngập", "intent": "maintenance", "urgency": "critical"},
    {"id": "general-question", "text": "Tôi cần hỏi thông tin hỗ trợ", "intent": "general", "urgency": "low"},
]


def classify(text: str) -> dict[str, str]:
    result = classify_agent({"safe_input": text, "supervisor_route": []})
    return {"intent": result["intent"], "urgency": result["urgency"]}


def score(field: str) -> dict[str, Any]:
    labels = sorted({case[field] for case in CASES})
    matrix = Counter((case[field], classify(case["text"])[field]) for case in CASES)
    correct = sum(matrix[label, label] for label in labels)
    per_label = {}
    for label in labels:
        actual = sum(matrix[label, predicted] for predicted in labels)
        predicted = sum(matrix[expected, label] for expected in labels)
        per_label[label] = {
            "support": actual,
            "precision": round(matrix[label, label] / predicted, 4) if predicted else 0.0,
            "recall": round(matrix[label, label] / actual, 4) if actual else 0.0,
        }
    return {
        "sample_count": len(CASES),
        "correct": correct,
        "accuracy": round(correct / len(CASES), 4),
        "per_label": per_label,
    }


def build_report() -> dict[str, Any]:
    predictions = [
        {"id": case["id"], "expected": {"intent": case["intent"], "urgency": case["urgency"]}, "predicted": classify(case["text"])}
        for case in CASES
    ]
    return {
        "dataset": "TENANT_ROUTING_GOLDEN_CASES",
        "evaluation": "deterministic offline classifier",
        "intent": score("intent"),
        "urgency": score("urgency"),
        "predictions": predictions,
    }


if __name__ == "__main__":
    print(json.dumps(build_report(), ensure_ascii=False, indent=2))
