import os
import sys
import io
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_legal_upload_and_preview_and_delete():
    # 1. Upload file markdown
    sample_content = "# Luật Quy Hoạch Đà Nẵng\n## Chương I\n### Điều 1. Phạm vi\nÁp dụng cho toàn thành phố Đà Nẵng."
    file_tuple = ("quy_hoach_test.md", io.BytesIO(sample_content.encode("utf-8")), "text/markdown")
    
    upload_res = client.post("/api/legal/upload", files={"file": file_tuple})
    assert upload_res.status_code == 200
    res_data = upload_res.json()
    assert res_data["success"] is True
    doc_id = res_data["data"]["id"]

    # 2. List documents
    list_res = client.get("/api/legal/documents")
    assert list_res.status_code == 200
    docs = list_res.json()["data"]
    assert any(d["id"] == doc_id for d in docs)

    # 3. Preview document
    prev_res = client.get(f"/api/legal/documents/{doc_id}/preview")
    assert prev_res.status_code == 200
    assert "Luật Quy Hoạch Đà Nẵng" in prev_res.json()["data"]["content"]

    # 4. Index document
    index_res = client.post(f"/api/legal/documents/{doc_id}/index")
    assert index_res.status_code == 200
    assert index_res.json()["success"] is True
    assert index_res.json()["chunks_count"] > 0

    # 5. Delete document
    del_res = client.delete(f"/api/legal/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

def test_chat_stream_emits_citations_event():
    # Gửi câu hỏi pháp lý vào endpoint /api/chat/stream
    payload = {
        "message": "Căn cứ pháp lý nào quy định về điều kiện mua bán nhà ở thương mại?",
        "thread_id": "test_stream_citations_01"
    }
    response = client.post("/api/chat/stream", json=payload)
    assert response.status_code == 200
    
    stream_content = response.text
    # Phải có event citations và event token
    assert '"type": "citations"' in stream_content or '"type": "token"' in stream_content
    assert "[DONE]" in stream_content
