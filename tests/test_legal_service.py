import os
import sys
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from legal_service import LegalService

@pytest.fixture
def legal_service():
    service = LegalService()
    # Đảm bảo collection tồn tại
    service.ensure_collection()
    return service

def test_save_and_list_document(legal_service, tmp_path):
    doc_meta = legal_service.save_document(
        filename="test_luat_dat_dai.md",
        content_md="# Luật Đất Đai 2024\n## Chương I\n### Điều 1. Phạm vi\nQuy định về đất đai."
    )
    assert doc_meta["filename"] == "test_luat_dat_dai.md"
    assert "id" in doc_meta

    docs = legal_service.list_documents()
    assert any(d["id"] == doc_meta["id"] for d in docs)

    preview = legal_service.get_document_preview(doc_meta["id"])
    assert "# Luật Đất Đai 2024" in preview

    # Dọn dẹp
    legal_service.delete_document(doc_meta["id"])

def test_index_and_search_legal_document(legal_service):
    # Ingest file sample đã có
    with open("backend/data/legal_docs/sample_luat_nha_o.md", "r", encoding="utf-8") as f:
        content = f.read()
    
    doc_meta = legal_service.save_document(
        filename="sample_luat_nha_o.md",
        content_md=content
    )
    
    chunk_count = legal_service.index_document(doc_meta["id"])
    assert chunk_count > 0

    # Test tìm kiếm về người nước ngoài mua nhà
    results = legal_service.search_legal_context("người nước ngoài có được mua căn hộ chung cư ở Đà Nẵng không?", top_k=3)
    assert len(results) > 0
    assert "article" in results[0]
    assert "content" in results[0]
    assert "doc_title" in results[0]
    
    # Test tìm kiếm về đặt cọc
    deposit_results = legal_service.search_legal_context("quy định về tiền đặt cọc mua nhà dự án", top_k=2)
    assert len(deposit_results) > 0
    assert any("đặt cọc" in r["content"].lower() or "165" in r["article"] for r in deposit_results)
