import os
import sys
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from legal_service import legal_service
from qdrant_service import qdrant_service


@pytest.fixture(scope="module", autouse=True)
def setup_rag_retrieval_collections():
    """Đảm bảo các collection cho văn bản luật và BĐS đã có dữ liệu mẫu trước khi test retrieval"""
    legal_service.ensure_collection()
    qdrant_service.ensure_collection()

    # Nạp dữ liệu mẫu luật nếu chưa có
    docs = legal_service.list_documents()
    sample_doc = next((d for d in docs if "sample_luat_nha_o" in d["id"]), None)
    if not sample_doc:
        sample_path = os.path.join(backend_dir, "data", "legal_docs", "sample_luat_nha_o.md")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as f:
                content = f.read()
            legal_service.save_document("sample_luat_nha_o.md", content, doc_id="sample_luat_nha_o")
            legal_service.index_document("sample_luat_nha_o")
    elif sample_doc.get("status") != "indexed":
        legal_service.index_document(sample_doc["id"])

    # Nạp dữ liệu mẫu BĐS nếu trống
    try:
        count_res = qdrant_service.client.count(collection_name=qdrant_service.collection_name, exact=True)
        if count_res.count == 0:
            qdrant_service.ingest_dataset()
    except Exception:
        qdrant_service.ingest_dataset()


def test_semantic_retrieval_finds_relevant_legal_articles():
    """
    Tầng 2: Kiểm thử tính chính xác của Semantic Retrieval trên collection danang_legal_docs.
    Query về quyền sở hữu nhà ở của người nước ngoài phải truy xuất đúng Điều 19 hoặc Điều liên quan.
    """
    query = "người nước ngoài có được mua căn hộ chung cư ở Đà Nẵng không?"
    results = legal_service.search_legal_context(query, top_k=3)

    assert len(results) > 0
    # Phải có metadata đầy đủ
    assert "article" in results[0]
    assert "content" in results[0]
    assert "doc_title" in results[0]
    assert "index" in results[0]

    # Kiểm tra ngữ cảnh có liên quan tới người nước ngoài
    found_foreign_clause = any(
        "19" in str(r.get("article", "")) or "nước ngoài" in r.get("content", "").lower()
        for r in results
    )
    assert found_foreign_clause, "Không tìm thấy điều khoản về quyền sở hữu của người nước ngoài"


def test_legal_chunk_deduplication():
    """
    Tầng 2: Kiểm thử cơ chế Deduplication ở tầng Retrieval.
    Kết quả trả về không được chứa hai chunk trùng lặp cùng một điều luật (article).
    """
    query = "thủ tục mua bán và công chứng hợp đồng đặt cọc nhà đất"
    results = legal_service.search_legal_context(query, top_k=4)

    assert len(results) > 0
    articles = [r.get("article") for r in results if r.get("article")]
    # Kiểm tra danh sách article là duy nhất
    assert len(articles) == len(set(articles)), f"Phát hiện điều luật trùng lặp: {articles}"


def test_property_search_structured_filtering():
    """
    Tầng 2: Kiểm thử Hybrid Search kết hợp bộ lọc có cấu trúc trên collection danang_properties.
    Lọc đồng thời theo quận, giá tối đa và số phòng ngủ tối thiểu.
    """
    # 1. Test lọc theo Quận
    district_target = "Sơn Trà"
    results_district = qdrant_service.search_properties(
        query="căn hộ gần biển",
        district=district_target,
        limit=3
    )
    for p in results_district:
        assert p.get("district") == district_target

    # 2. Test lọc theo Giá tối đa (max_price tính theo tỷ VNĐ)
    max_price_ty = 3.0
    results_price = qdrant_service.search_properties(
        query="nhà phố giá rẻ",
        max_price=max_price_ty,
        limit=3
    )
    for p in results_price:
        assert p.get("price_vnd", 0) <= max_price_ty * 1_000_000_000

    # 3. Test lọc theo số phòng ngủ tối thiểu
    min_beds = 2
    results_beds = qdrant_service.search_properties(
        query="căn hộ gia đình",
        min_bedrooms=min_beds,
        limit=3
    )
    for p in results_beds:
        assert p.get("bedrooms", 0) >= min_beds


def test_zero_hit_and_empty_query_fallback():
    """
    Tầng 2: Kiểm thử biên khi truy vấn không có kết quả phù hợp (Zero-hit).
    Hệ thống phải trả về danh sách rỗng [] an toàn, không raise lỗi Unhandled Exception.
    """
    # Lọc giá phi thực tế (0.0001 tỷ = 100k VNĐ)
    results_empty = qdrant_service.search_properties(
        query="biệt thự biển triệu đô",
        max_price=0.0001,
        limit=3
    )
    assert isinstance(results_empty, list)
    assert len(results_empty) == 0

    # Lọc quận không tồn tại trong DB Đà Nẵng
    results_nonexistent = qdrant_service.search_properties(
        query="nhà phố",
        district="Quận Hoàn Kiếm",
        limit=3
    )
    assert isinstance(results_nonexistent, list)
    assert len(results_nonexistent) == 0
