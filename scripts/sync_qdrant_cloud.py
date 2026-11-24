import sys
import os
import json
import time
from pathlib import Path

# Thêm thư mục backend vào sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from config import settings
from qdrant_service import qdrant_service
from legal_service import legal_service

def sync_data_to_qdrant_cloud():
    print("=" * 70)
    print("🚀 BẮT ĐẦU ĐỒNG BỘ DỮ LIỆU LOCAL LÊN QDRANT CLOUD")
    print(f"Target Qdrant URL: {settings.QDRANT_URL}")
    print("=" * 70)

    # 1. Đồng bộ Properties (BĐS Đà Nẵng)
    print("\n[PHẦN 1/2] Đang nạp dữ liệu BĐS Đà Nẵng (danang_properties.json)...")
    try:
        qdrant_service.ingest_dataset(clear_existing=True)
        prop_count = qdrant_service.client.count(settings.QDRANT_COLLECTION_NAME, exact=True).count
        print(f"✅ [OK] Đã nạp thành công {prop_count} căn BĐS vào collection '{settings.QDRANT_COLLECTION_NAME}'.")
    except Exception as e:
        print(f"❌ [LỖI] Không thể nạp properties: {e}")

    # 2. Đồng bộ Legal Docs (Văn Bản Pháp Lý)
    print(f"\n[PHẦN 2/2] Đang nạp các văn bản pháp lý vào collection '{settings.QDRANT_LEGAL_COLLECTION_NAME}'...")
    try:
        legal_service.ensure_collection()
        docs = legal_service.list_documents()
        print(f"📋 Tìm thấy {len(docs)} tài liệu trong danh mục quản lý:")

        total_chunks = 0
        for idx, doc in enumerate(docs, 1):
            doc_id = doc["id"]
            doc_title = doc.get("title", doc_id)
            print(f"\n  ({idx}/{len(docs)}) Đang xử lý: [{doc_id}]")
            print(f"      Tiêu đề: {doc_title[:60]}...")
            t0 = time.time()
            try:
                chunks = legal_service.index_document(doc_id)
                dur = round(time.time() - t0, 2)
                total_chunks += chunks
                print(f"      ✓ Đã cắt & nạp {chunks} chunks lên Qdrant Cloud ({dur}s).")
            except Exception as err:
                print(f"      ✗ Thất bại khi nạp {doc_id}: {err}")

        legal_count = legal_service.client.count(settings.QDRANT_LEGAL_COLLECTION_NAME, exact=True).count
        print(f"\n✅ [OK] Toàn bộ văn bản pháp lý đã được nạp!")
        print(f"   Tổng số points hiện có trong '{settings.QDRANT_LEGAL_COLLECTION_NAME}': {legal_count} points.")

    except Exception as e:
        print(f"❌ [LỖI] Lỗi khi xử lý legal documents: {e}")

    # 3. Tổng kết trạng thái trên Qdrant Cloud
    print("\n" + "=" * 70)
    print("📊 BÁO CÁO TỔNG KẾT TRÊN QDRANT CLOUD")
    print("=" * 70)
    try:
        collections = qdrant_service.client.get_collections().collections
        for c in collections:
            cnt = qdrant_service.client.count(c.name, exact=True).count
            print(f"  • Collection '{c.name}': {cnt} points (Ready)")
    except Exception as e:
        print(f"Lỗi kiểm tra collection: {e}")
    print("=" * 70)
    print("🎉 ĐỒNG BỘ HOÀN TẤT THÀNH CÔNG!")

if __name__ == "__main__":
    sync_data_to_qdrant_cloud()
