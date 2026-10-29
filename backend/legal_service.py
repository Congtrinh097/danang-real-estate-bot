import os
import sys
import json
import uuid
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

backend_dir = str(Path(__file__).resolve().parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter

from config import settings
from qdrant_service import qdrant_service


class LegalService:
    def __init__(self):
        self.collection_name = getattr(settings, "QDRANT_LEGAL_COLLECTION_NAME", "danang_legal_docs")
        self.vector_size = 1536
        self.client = qdrant_service.client
        self.embeddings = qdrant_service.embeddings

        # Thư mục lưu trữ văn bản pháp lý
        backend_dir = Path(__file__).resolve().parent
        self.storage_dir = backend_dir / "data" / "legal_docs"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.storage_dir / "documents_meta.json"

        if not self.meta_file.exists():
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def ensure_collection(self):
        """Tạo collection Qdrant cho văn bản pháp lý nếu chưa tồn tại"""
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in collections:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                )
                print(f"[OK] Collection created: {self.collection_name}")
        except Exception as e:
            print(f"[WARN] Error ensuring legal collection: {e}")

    def list_documents(self) -> List[Dict[str, Any]]:
        """Lấy danh sách siêu dữ liệu các tài liệu đã nạp"""
        try:
            with open(self.meta_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_document(self, filename: str, content_md: str, doc_id: Optional[str] = None) -> Dict[str, Any]:
        """Lưu nội dung Markdown và cập nhật metadata"""
        if not doc_id:
            # Tạo doc_id từ tên file hoặc uuid
            clean_name = Path(filename).stem.lower().replace(" ", "_").replace("-", "_")
            doc_id = f"{clean_name}_{uuid.uuid4().hex[:6]}"

        file_path = self.storage_dir / f"{doc_id}.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content_md)

        # Trích xuất tiêu đề đầu tiên từ file MD làm title
        title = filename
        for line in content_md.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                title = line.replace("# ", "").strip()
                break

        doc_meta = {
            "id": doc_id,
            "filename": filename,
            "title": title,
            "size": len(content_md.encode("utf-8")),
            "uploaded_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending",  # pending | indexed
            "chunks_count": 0
        }

        docs = self.list_documents()
        # Cập nhật nếu đã có, hoặc thêm mới
        docs = [d for d in docs if d.get("id") != doc_id]
        docs.insert(0, doc_meta)

        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)

        return doc_meta

    def get_document_preview(self, doc_id: str) -> str:
        """Đọc toàn văn Markdown của tài liệu"""
        file_path = self.storage_dir / f"{doc_id}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"Không tìm thấy tài liệu với ID: {doc_id}")
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def index_document(self, doc_id: str) -> int:
        """Cắt chunk theo cấu trúc Điều/Khoản và nạp vào Qdrant"""
        self.ensure_collection()
        content = self.get_document_preview(doc_id)
        docs = self.list_documents()
        current_meta = next((d for d in docs if d["id"] == doc_id), None)
        doc_title = current_meta.get("title", doc_id) if current_meta else doc_id

        # Cắt đoạn theo Markdown Header
        headers_to_split_on = [
            ("#", "doc_title"),
            ("##", "chapter"),
            ("###", "article"),
        ]
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False
        )
        splits = markdown_splitter.split_text(content)

        # Xoá vector cũ của doc_id này nếu có
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                )
            )
        except Exception:
            pass

        points = []
        for idx, split in enumerate(splits):
            chunk_text = split.page_content.strip()
            if not chunk_text:
                continue

            metadata = split.metadata
            article = metadata.get("article", "")
            chapter = metadata.get("chapter", "")
            chunk_doc_title = metadata.get("doc_title", doc_title)

            # Tính vector embedding
            if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"):
                vector = qdrant_service.embed_query_safe(chunk_text)
            else:
                import hashlib
                import random
                seed = int(hashlib.sha256(f"{doc_id}_{idx}".encode("utf-8")).hexdigest(), 16) % (10**6)
                rng = random.Random(seed)
                vector = [rng.uniform(-0.1, 0.1) for _ in range(self.vector_size)]

            # Sinh UUID chuẩn cho Qdrant point
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_{idx}"))
            points.append(PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "doc_id": doc_id,
                    "doc_title": chunk_doc_title,
                    "chapter": chapter,
                    "article": article,
                    "content": chunk_text
                }
            ))

        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

        # Cập nhật metadata trạng thái
        for d in docs:
            if d["id"] == doc_id:
                d["status"] = "indexed"
                d["chunks_count"] = len(points)
                break

        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)

        return len(points)

    def delete_document(self, doc_id: str) -> bool:
        """Xoá tài liệu khỏi đĩa và xoá vector khỏi Qdrant"""
        self.ensure_collection()
        # 1. Xoá points trong Qdrant
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                )
            )
        except Exception as e:
            print(f"[WARN] Failed to delete points in Qdrant for {doc_id}: {e}")

        # 2. Xoá file md
        file_path = self.storage_dir / f"{doc_id}.md"
        if file_path.exists():
            file_path.unlink()

        # 3. Cập nhật documents_meta.json
        docs = self.list_documents()
        docs = [d for d in docs if d["id"] != doc_id]
        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)

        return True

    def search_legal_context(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Tìm kiếm các đoạn văn bản luật liên quan nhất tới câu hỏi"""
        self.ensure_collection()
        if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"):
            query_vector = qdrant_service.embed_query_safe(query)
        else:
            # Deterministic mock fallback
            import hashlib
            import random
            seed = int(hashlib.sha256(query.encode("utf-8")).hexdigest(), 16) % (10**6)
            rng = random.Random(seed)
            query_vector = [rng.uniform(-0.1, 0.1) for _ in range(self.vector_size)]

        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k
        )

        formatted = []
        for idx, hit in enumerate(search_result):
            payload = hit.payload or {}
            formatted.append({
                "index": idx + 1,
                "id": hit.id,
                "doc_id": payload.get("doc_id", ""),
                "doc_title": payload.get("doc_title", "Văn bản Luật"),
                "chapter": payload.get("chapter", ""),
                "article": payload.get("article", ""),
                "content": payload.get("content", ""),
                "score": round(float(hit.score), 4)
            })

        return formatted

# Khởi tạo singleton
legal_service = LegalService()
