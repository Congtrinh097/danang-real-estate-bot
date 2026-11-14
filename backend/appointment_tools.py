import contextvars
from typing import Optional, List, Dict, Any
from langchain.tools import tool
from appointment_service import appointment_service

# Context variable lưu user_id hiện tại của request (thread-safe và async-safe)
current_user_id_cv = contextvars.ContextVar("current_user_id", default="default_user")

def set_current_user_id(user_id: str):
    """Thiết lập user_id cho ngữ cảnh request hiện tại"""
    current_user_id_cv.set(user_id)

def get_current_user_id() -> str:
    """Lấy user_id trong ngữ cảnh hiện tại"""
    return current_user_id_cv.get()

@tool
def book_viewing_appointment(
    name: str,
    phone: str,
    viewing_time: str,
    property_title: str = "",
    note: str = ""
) -> str:
    """Lưu lịch hẹn xem nhà vào cơ sở dữ liệu sau khi khách hàng đã cung cấp đủ thông tin và đồng ý xác nhận.
    Args:
        name: Họ và tên của khách hàng (ví dụ: 'Nguyễn Văn Tuấn').
        phone: Số điện thoại hoặc Zalo liên hệ (ví dụ: '0905123456').
        viewing_time: Thời gian hẹn cụ thể (ví dụ: '15:00 chiều thứ Bảy ngày 15/11', '10h sáng mai').
        property_title: Tên hoặc đặc điểm căn hộ / BĐS muốn xem (ví dụ: 'Căn hộ Monarchy 2PN', 'Nhà phố Hải Châu').
        note: Ghi chú thêm từ khách hàng (nếu có).
    """
    user_id = get_current_user_id()
    try:
        appt = appointment_service.create_appointment(
            user_id=user_id,
            customer_name=name,
            customer_phone=phone,
            viewing_time=viewing_time,
            property_title=property_title,
            note=note
        )
        return (
            f"✅ ĐÃ ĐẶT LỊCH HẸN THÀNH CÔNG!\n"
            f"- Mã lịch hẹn: #{appt['id']}\n"
            f"- Khách hàng: {appt['customer_name']}\n"
            f"- Số điện thoại: {appt['customer_phone']}\n"
            f"- Thời gian xem nhà: {appt['viewing_time']}\n"
            f"- Bất động sản: {appt['property_title'] or 'Theo tư vấn trong chat'}\n"
            f"- Ghi chú: {appt['note'] or 'Không có'}\n"
            f"- Trạng thái: Đã xác nhận"
        )
    except Exception as e:
        return f"❌ Lỗi khi lưu lịch hẹn vào cơ sở dữ liệu: {str(e)}"

@tool
def get_user_appointments(status: Optional[str] = None) -> str:
    """Tra cứu tất cả các lịch hẹn xem nhà mà người dùng hiện tại đã đặt trong hệ thống.
    Args:
        status: Lọc theo trạng thái ('confirmed' - đã xác nhận, 'cancelled' - đã hủy, hoặc để trống để lấy tất cả).
    """
    user_id = get_current_user_id()
    try:
        appts = appointment_service.get_user_appointments(user_id=user_id, status=status)
        if not appts:
            return "Dạ hiện tại anh/chị chưa có lịch hẹn xem nhà nào được lưu trong hệ thống ạ."
        
        result_lines = [f"📋 DANH SÁCH LỊCH HẸN CỦA ANH/CHỊ ({len(appts)} lịch):"]
        for a in appts:
            st_text = "Đã xác nhận" if a["status"] == "confirmed" else ("Đã hủy" if a["status"] == "cancelled" else a["status"])
            result_lines.append(
                f"- [Mã #{a['id']}] {a['property_title'] or 'Xem nhà thực tế'}\n"
                f"  • Thời gian: {a['viewing_time']}\n"
                f"  • Khách: {a['customer_name']} - SĐT: {a['customer_phone']}\n"
                f"  • Trạng thái: {st_text}\n"
                f"  • Ghi chú: {a['note'] or 'Không có'}"
            )
        return "\n".join(result_lines)
    except Exception as e:
        return f"❌ Lỗi khi tra cứu lịch hẹn: {str(e)}"

@tool
def update_appointment(
    appointment_id: int,
    new_time: Optional[str] = None,
    new_note: Optional[str] = None
) -> str:
    """Cập nhật hoặc dời thời gian / sửa ghi chú của một lịch hẹn xem nhà đã đặt theo mã lịch hẹn.
    Args:
        appointment_id: Mã số ID của lịch hẹn cần sửa (ví dụ: 1, 2, 3).
        new_time: Thời gian hẹn mới (ví dụ: '16h30 ngày mai', '14:00 Chủ nhật').
        new_note: Ghi chú mới hoặc bổ sung.
    """
    user_id = get_current_user_id()
    try:
        updated = appointment_service.update_appointment(
            appointment_id=appointment_id,
            user_id=user_id,
            new_time=new_time,
            new_note=new_note
        )
        if not updated:
            return f"❌ Không tìm thấy lịch hẹn mã #{appointment_id} của anh/chị để cập nhật."
        
        return (
            f"✅ ĐÃ CẬP NHẬT LỊCH HẸN #{appointment_id} THÀNH CÔNG!\n"
            f"- Thời gian mới: {updated['viewing_time']}\n"
            f"- BĐS: {updated['property_title'] or 'Theo tư vấn'}\n"
            f"- Ghi chú: {updated['note'] or 'Không có'}\n"
            f"- Trạng thái: Đã cập nhật"
        )
    except Exception as e:
        return f"❌ Lỗi khi cập nhật lịch hẹn: {str(e)}"

@tool
def cancel_appointment(appointment_id: int, reason: str = "") -> str:
    """Hủy một lịch hẹn xem nhà đã đặt theo mã lịch hẹn của khách hàng.
    Args:
        appointment_id: Mã số ID của lịch hẹn cần hủy (ví dụ: 1, 2).
        reason: Lý do khách muốn hủy lịch (ví dụ: 'Bận đột xuất', 'Đã tìm được nhà khác').
    """
    user_id = get_current_user_id()
    try:
        cancelled = appointment_service.cancel_appointment(
            appointment_id=appointment_id,
            user_id=user_id,
            reason=reason
        )
        if not cancelled:
            return f"❌ Không tìm thấy lịch hẹn mã #{appointment_id} của anh/chị để hủy."
        
        return (
            f"✅ ĐÃ HỦY LỊCH HẸN #{appointment_id} THÀNH CÔNG!\n"
            f"- Khách hàng: {cancelled['customer_name']}\n"
            f"- BĐS: {cancelled['property_title'] or 'Xem nhà'}\n"
            f"- Trạng thái: Đã hủy\n"
            f"- Ghi chú / Lý do: {reason or 'Khách yêu cầu hủy'}"
        )
    except Exception as e:
        return f"❌ Lỗi khi hủy lịch hẹn: {str(e)}"

appointment_tools = [
    book_viewing_appointment,
    get_user_appointments,
    update_appointment,
    cancel_appointment
]
