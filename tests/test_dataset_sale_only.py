import json
import os
import pytest

PROPERTIES_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "data", "danang_properties.json"))

def test_dataset_contains_only_sale_properties():
    """
    TDD Test:
    1. Tập dữ liệu danang_properties.json chỉ chứa BĐS mua bán (category == 'sale').
    2. Tuyệt đối không chứa bất kỳ mục nào có category == 'rent'.
    3. Có tối thiểu 15 BĐS bán để phục vụ tra cứu đa dạng phân khúc.
    4. Đại diện đầy đủ cho 7 quận/huyện của TP. Đà Nẵng:
       - Hải Châu, Sơn Trà, Ngũ Hành Sơn, Thanh Khê, Cẩm Lệ, Liên Chiểu, Hòa Vang.
    """
    assert os.path.exists(PROPERTIES_PATH), f"File không tồn tại: {PROPERTIES_PATH}"

    with open(PROPERTIES_PATH, "r", encoding="utf-8") as f:
        properties = json.load(f)

    assert isinstance(properties, list)
    assert len(properties) >= 15, f"Số lượng BĐS bán quá ít: {len(properties)} < 15"

    all_districts = set()
    for item in properties:
        assert item.get("category") == "sale", f"Phát hiện item không phải mua bán: {item.get('id')} có category={item.get('category')}"
        assert not item.get("id", "").startswith("dn-rent-"), f"Phát hiện ID thuê chưa xóa: {item.get('id')}"
        assert item.get("price", 0) > 0, f"Giá BĐS không hợp lệ: {item.get('id')}"
        assert item.get("area_m2", 0) > 0, f"Diện tích không hợp lệ: {item.get('id')}"
        assert item.get("property_type") in ["apartment", "house", "land", "villa"], f"Loại hình không hợp lệ: {item.get('property_type')}"
        assert item.get("district"), f"Thiếu quận: {item.get('id')}"
        all_districts.add(item.get("district"))

    expected_districts = {
        "Hải Châu", "Sơn Trà", "Ngũ Hành Sơn", "Thanh Khê", "Cẩm Lệ", "Liên Chiểu", "Hòa Vang"
    }
    missing = expected_districts - all_districts
    assert not missing, f"Thiếu các quận trong dataset bán: {missing}"
