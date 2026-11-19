import pytest
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from a2a_council import CouncilSpeaker, CouncilDebateTurn, CouncilVerdict

def test_council_schema_validation():
    turn = CouncilDebateTurn(
        speaker=CouncilSpeaker.PROPERTY_EXPERT,
        title="Đánh giá quỹ căn Hải Châu",
        content="Tìm thấy căn Monarchy giá 3.5 tỷ.",
        key_points=["Vị trí trung tâm", "Phù hợp ngân sách"],
        timestamp=1700000000.0
    )
    assert turn.speaker == CouncilSpeaker.PROPERTY_EXPERT
    assert len(turn.key_points) == 2

    verdict = CouncilVerdict(
        overall_feasibility="caution_required",
        feasibility_score=68,
        summary_recommendation="Nên cân nhắc nới lỏng ngân sách hoặc chọn căn 2PN.",
        legal_risks=["Chờ kiểm tra PCCC"],
        critic_caveats=["Mùa thấp điểm dòng tiền âm 8 triệu/tháng"],
        action_checklist=["Thương lượng giá", "Xin bảng kê thanh toán"]
    )
    assert verdict.overall_feasibility == "caution_required"
    assert verdict.feasibility_score == 68
