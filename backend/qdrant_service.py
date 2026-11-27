import json
import os
import sys
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, Range
from langchain_openai import OpenAIEmbeddings
from config import settings
from agentops import spend_ledger, UsageEvent, TraceContext
import time

class QdrantService:
    def __init__(self):
        self.client = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = 1536  # Chuẩn của text-embedding-3-small

        # Thử kết nối Qdrant từ xa (Docker hoặc Qdrant Cloud) trước
        try:
            client_kwargs = {"url": settings.QDRANT_URL, "timeout": 3.0}
            if getattr(settings, "QDRANT_API_KEY", None):
                client_kwargs["api_key"] = settings.QDRANT_API_KEY
            temp_client = QdrantClient(**client_kwargs)
            temp_client.get_collections()
            self.client = temp_client
            print(f"[INFO] Connected to Remote Qdrant at {settings.QDRANT_URL}")
        except Exception as e:
            # Nếu không kết nối được Qdrant từ xa, tự động fallback sang Qdrant Local file storage
            print(f"[INFO] Remote Qdrant not available ({e}). Using local file-based Qdrant storage...")
            local_path = os.path.abspath("./data/qdrant_local")
            os.makedirs(local_path, exist_ok=True)
            self.client = QdrantClient(path=local_path)

        embeddings_kwargs = {
            "model": settings.EMBEDDING_MODEL_NAME,
            "api_key": settings.OPENAI_API_KEY or "dummy_key_if_mock"
        }
        if settings.OPENAI_BASE_URL:
            embeddings_kwargs["base_url"] = settings.OPENAI_BASE_URL

        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)
        self.fallback_embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY or "dummy_key_if_mock",
            base_url=settings.FALLBACK_OPENAI_BASE_URL or "https://api.openai.com/v1"
        )

    def _track_embedding_usage(self, texts: List[str], latency_ms: int):
        """Ghi nhận token và chi phí embedding vào AgentOps spend ledger"""
        try:
            total_chars = sum(len(t) for t in texts)
            # Ước tính token cho embedding (tiếng Việt/Anh trung bình ~2 ký tự / token)
            est_tokens = max(int(total_chars / 2.2), len(texts) * 8)
            event = UsageEvent.from_llm_output(
                request_id=TraceContext.get_request_id(),
                thread_id=TraceContext.get_thread_id(),
                agent_name="QdrantEmbeddingService",
                model_name=settings.EMBEDDING_MODEL_NAME,
                token_usage={"prompt_tokens": est_tokens, "completion_tokens": 0},
                latency_ms=latency_ms,
                workload_type=TraceContext.get_workload_type() or "chat",
                execution_status="SUCCESS"
            )
            spend_ledger.record_usage_and_spend(event)
        except Exception as e:
            print(f"[WARN] Failed to record embedding usage: {e}")

    def embed_query_safe(self, text: str) -> List[float]:
        """Tạo vector với cơ chế fallback tự động nếu base_url lỗi"""
        t0 = time.time()
        try:
            vec = self.embeddings.embed_query(text)
        except Exception:
            vec = self.fallback_embeddings.embed_query(text)
        latency = int((time.time() - t0) * 1000)
        self._track_embedding_usage([text], latency)
        return vec

    def embed_documents_safe(self, texts: List[str]) -> List[List[float]]:
        """Tạo batch vector với cơ chế fallback tự động nếu base_url lỗi"""
        t0 = time.time()
        try:
            vecs = self.embeddings.embed_documents(texts)
        except Exception:
            vecs = self.fallback_embeddings.embed_documents(texts)
        latency = int((time.time() - t0) * 1000)
        self._track_embedding_usage(texts, latency)
        return vecs

    def ensure_collection(self):
        """Khởi tạo collection nếu chưa tồn tại kèm theo payload indices"""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
            print(f"[OK] Collection created: {self.collection_name}")

        # Đảm bảo các trường filter có payload index để tương thích với Qdrant Cloud
        for field, schema in [
            ("category", "keyword"),
            ("district", "keyword"),
            ("price", "integer"),
            ("price_vnd", "integer"),
            ("bedrooms", "integer")
        ]:
            try:
                self.client.create_payload_index(collection_name=self.collection_name, field_name=field, field_schema=schema)
            except Exception:
                pass

    def ingest_dataset(self, json_file_path: Optional[str] = None, clear_existing: bool = False):
        """Nạp dữ liệu BĐS vào Qdrant với cơ chế an toàn: kiểm tra collection hiện có để tránh nạp lặp lãng phí token OpenAI"""
        self.ensure_collection()

        # Nếu không yêu cầu xóa và collection đã có dữ liệu, bỏ qua để tiết kiệm token embedding
        if not clear_existing:
            try:
                count_res = self.client.count(collection_name=self.collection_name, exact=True)
                if count_res.count > 0:
                    print(f"[INFO] Collection '{self.collection_name}' already contains {count_res.count} points. Skipping re-ingestion to save OpenAI tokens.")
                    return
            except Exception as e:
                print(f"[WARN] Unable to check collection count: {e}")

        if json_file_path is None or not os.path.exists(json_file_path):
            base_data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "danang_properties.json"))
            if os.path.exists(base_data_path):
                json_file_path = base_data_path
            elif json_file_path and os.path.exists(json_file_path):
                pass
            else:
                json_file_path = "./data/danang_properties.json"

        if clear_existing:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name in collections:
                self.client.delete_collection(collection_name=self.collection_name)
                print(f"[INFO] Cleared old collection: {self.collection_name}")
                self.ensure_collection()
        with open(json_file_path, "r", encoding="utf-8") as f:
            properties = json.load(f)

        points = []
        for idx, item in enumerate(properties):
            full_text = f"{item['title']}. {item['description']} Vi tri: {item.get('ward', '')}, {item.get('district', '')}, Da Nang."
            
            if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"):
                vector = self.embed_query_safe(full_text)
            else:
                import hashlib
                import random
                seed = int(hashlib.sha256(item['id'].encode('utf-8')).hexdigest(), 16) % (10**6)
                rng = random.Random(seed)
                vector = [rng.uniform(-0.1, 0.1) for _ in range(self.vector_size)]

            point = PointStruct(
                id=idx + 1,
                vector=vector,
                payload=item
            )
            points.append(point)

        self.client.upsert(collection_name=self.collection_name, points=points)
        print(f"[OK] Ingested {len(points)} properties into Qdrant.")

    def search_properties(
        self,
        query: str,
        category: Optional[str] = "sale",
        district: Optional[str] = None,
        max_price: Optional[float] = None,
        min_bedrooms: Optional[int] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Truy vấn Vector kết hợp Payload Filter"""
        must_conditions = []

        if category:
            must_conditions.append(
                FieldCondition(key="category", match=MatchValue(value=category))
            )
        if district:
            must_conditions.append(
                FieldCondition(key="district", match=MatchValue(value=district))
            )
        if max_price:
            norm_price = int(max_price * 1_000_000_000) if max_price <= 1000 else int(max_price)
            must_conditions.append(
                FieldCondition(key="price", range=Range(lte=norm_price))
            )
        if min_bedrooms:
            must_conditions.append(
                FieldCondition(key="bedrooms", range=Range(gte=min_bedrooms))
            )

        qdrant_filter = Filter(must=must_conditions) if must_conditions else None

        if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"):
            query_vector = self.embed_query_safe(query)
        else:
            import random
            rng = random.Random(42)
            query_vector = [rng.uniform(-0.1, 0.1) for _ in range(self.vector_size)]

        if hasattr(self.client, "search"):
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=limit
            )
            return [hit.payload for hit in results]
        else:
            # Qdrant client phiên bản mới dùng query_points
            res = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=limit
            )
            return [hit.payload for hit in res.points]

qdrant_service = QdrantService()

if __name__ == "__main__":
    qdrant_service.ingest_dataset()
    test_search = qdrant_service.search_properties(
        query="căn hộ gần biển",
        district="Sơn Trà"
    )
    print("Found:", len(test_search))
