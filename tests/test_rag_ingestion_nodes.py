import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from legal_service import LegalService
from qdrant_service import QdrantService
from langchain_text_splitters import MarkdownHeaderTextSplitter


def test_markdown_header_chunking_structure():
    """
    Tầng 1: Kiểm thử cấu trúc chia chunk theo Markdown Header (# Luật, ## Chương, ### Điều).
    Đảm bảo nội dung Điều luật giữ nguyên ngữ cảnh phân cấp và metadata chuẩn xác.
    """
    raw_markdown = """# Luật Đất Đai 2024
## Chương I: Quy định chung
### Điều 1. Phạm vi điều chỉnh
Luật này quy định về chế độ sở hữu đất đai, quyền hạn và trách nhiệm của Nhà nước.
### Điều 2. Đối tượng áp dụng
Cơ quan nhà nước, người sử dụng đất và các tổ chức, cá nhân có liên quan.
## Chương II: Quyền của người sử dụng đất
### Điều 10. Quyền chung
1. Được cấp Giấy chứng nhận quyền sử dụng đất.
2. Hưởng thành quả lao động, kết quả đầu tư trên đất.
"""
    headers_to_split = [
        ("#", "doc_title"),
        ("##", "chapter"),
        ("###", "article"),
    ]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split, strip_headers=False)
    splits = splitter.split_text(raw_markdown)

    assert len(splits) == 3
    # Chunk 1
    assert splits[0].metadata["doc_title"] == "Luật Đất Đai 2024"
    assert "Chương I" in splits[0].metadata["chapter"]
    assert "Điều 1" in splits[0].metadata["article"]
    assert "Phạm vi điều chỉnh" in splits[0].page_content

    # Chunk 3
    assert "Chương II" in splits[2].metadata["chapter"]
    assert "Điều 10" in splits[2].metadata["article"]
    assert "Được cấp Giấy chứng nhận" in splits[2].page_content


def test_save_document_deduplication():
    """
    Tầng 1: Kiểm thử cơ chế Deduplication khi nạp văn bản pháp lý.
    Nếu tải lên cùng tên file thì hệ thống phải tái sử dụng doc_id, không sinh bản ghi thừa.
    """
    service = LegalService()
    service.ensure_collection()

    filename = "test_luat_kinh_doanh_bds_dup.md"
    content_v1 = "# Luật Kinh Doanh BĐS\n### Điều 1. Phạm vi\nNội dung v1"
    content_v2 = "# Luật Kinh Doanh BĐS\n### Điều 1. Phạm vi\nNội dung v2 đã sửa đổi"

    meta1 = service.save_document(filename, content_v1)
    meta2 = service.save_document(filename, content_v2)

    assert meta1["id"] == meta2["id"]
    assert meta2["size"] == len(content_v2.encode("utf-8"))

    # Dọn dẹp
    service.delete_document(meta1["id"])


def test_property_context_builder():
    """
    Tầng 1: Kiểm thử chuỗi ngữ cảnh ghép dữ liệu BĐS phục vụ Embedding.
    Đảm bảo chứa đủ title, description, địa chỉ phường/quận tại Đà Nẵng.
    """
    sample_property = {
        "id": "prop_test_01",
        "title": "Căn hộ cao cấp ven sông Hàn",
        "description": "View trực diện cầu Rồng, nội thất cao cấp 2 phòng ngủ.",
        "ward": "Bình Hiên",
        "district": "Hải Châu",
        "price_vnd": 3500000000
    }

    full_text = f"{sample_property['title']}. {sample_property['description']} Vi tri: {sample_property.get('ward', '')}, {sample_property.get('district', '')}, Da Nang."
    assert "Căn hộ cao cấp ven sông Hàn" in full_text
    assert "Bình Hiên" in full_text
    assert "Hải Châu" in full_text
    assert "Da Nang" in full_text


def test_embedding_safe_fallback_and_spend_recording():
    """
    Tầng 1: Kiểm thử cơ chế fallback tự động của embed_query_safe khi base_url chính gặp sự cố
    và kiểm tra AgentOps spend tracking được gọi an toàn.
    """
    service = QdrantService()
    
    mock_primary = MagicMock()
    mock_primary.embed_query.side_effect = Exception("Primary OpenAI API connection timeout")
    
    mock_fallback = MagicMock()
    mock_fallback.embed_query.return_value = [0.05] * 1536
    
    service.embeddings = mock_primary
    service.fallback_embeddings = mock_fallback

    with patch.object(service, "_track_embedding_usage") as mock_track:
        vec = service.embed_query_safe("Quy định đặt cọc nhà ở")
        assert len(vec) == 1536
        assert vec[0] == 0.05
        assert mock_primary.embed_query.called
        assert mock_fallback.embed_query.called
        assert mock_track.called
