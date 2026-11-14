import sys
import os
import pytest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from appointment_service import appointment_service
from appointment_tools import (
    book_viewing_appointment,
    get_user_appointments,
    update_appointment,
    cancel_appointment,
    set_current_user_id,
    get_current_user_id
)

def test_appointment_crud():
    test_uid = "test_user_unit_001"
    set_current_user_id(test_uid)
    assert get_current_user_id() == test_uid

    # 1. Test create
    appt = appointment_service.create_appointment(
        user_id=test_uid,
        customer_name="Trần Văn Nam",
        customer_phone="0987654321",
        viewing_time="09:00 sáng Thứ Bảy",
        property_title="Căn hộ Hiyori Sơn Trà",
        note="Gặp tại sảnh tòa nhà"
    )
    assert appt is not None
    assert appt["customer_name"] == "Trần Văn Nam"
    assert appt["user_id"] == test_uid
    appt_id = appt["id"]

    # 2. Test get
    appts = appointment_service.get_user_appointments(test_uid)
    assert len(appts) >= 1
    found = [a for a in appts if a["id"] == appt_id]
    assert len(found) == 1
    assert found[0]["status"] == "confirmed"

    # 3. Test update
    updated = appointment_service.update_appointment(
        appointment_id=appt_id,
        user_id=test_uid,
        new_time="15:00 chiều Chủ Nhật",
        new_note="Đổi giờ sang buổi chiều"
    )
    assert updated is not None
    assert updated["viewing_time"] == "15:00 chiều Chủ Nhật"
    assert "Đổi giờ" in updated["note"]

    # 4. Test cancel
    cancelled = appointment_service.cancel_appointment(
        appointment_id=appt_id,
        user_id=test_uid,
        reason="Khách có việc bận"
    )
    assert cancelled is not None
    assert cancelled["status"] == "cancelled"

def test_appointment_tools():
    test_uid = "test_user_unit_002"
    set_current_user_id(test_uid)

    # 1. Tool Book appointment
    book_res = book_viewing_appointment.invoke({
        "name": "Lê Thị Thảo",
        "phone": "0912334455",
        "viewing_time": "14h chiều mai",
        "property_title": "Nhà phố Hải Châu",
        "note": "Cần xem kỹ pháp lý sổ hồng"
    })
    assert "ĐÃ ĐẶT LỊCH HẸN THÀNH CÔNG" in book_res
    assert "Lê Thị Thảo" in book_res

    # 2. Tool Get appointments
    get_res = get_user_appointments.invoke({})
    assert "DANH SÁCH LỊCH HẸN CỦA ANH/CHỊ" in get_res
    assert "Lê Thị Thảo" in get_res

    # 3. Tool Update appointment (extract ID from db)
    appts = appointment_service.get_user_appointments(test_uid)
    target_id = appts[0]["id"]

    update_res = update_appointment.invoke({
        "appointment_id": target_id,
        "new_time": "16h30 chiều mai",
        "new_note": "Chuyển sang 16h30"
    })
    assert "ĐÃ CẬP NHẬT LỊCH HẸN" in update_res
    assert "16h30 chiều mai" in update_res

    # 4. Tool Cancel appointment
    cancel_res = cancel_appointment.invoke({
        "appointment_id": target_id,
        "reason": "Khách dời sang tuần sau"
    })
    assert "ĐÃ HỦY LỊCH HẸN" in cancel_res
    assert "Đã hủy" in cancel_res
