import json
import os
import sys
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, Range
from langchain_openai import OpenAIEmbeddings
from config import settings

class QdrantService:
    def __init__(self):
        self.client = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = 1536  # Chuẩn của text-embedding-3-small

        # Thử kết nối Docker Qdrant trước (nếu Docker đang chạy)
        try:
            temp_client = QdrantClient(url=settings.QDRANT_URL, timeout=1.0)
            temp_client.get_collections()
            self.client = temp_client
            print("[INFO] Connected to Qdrant Docker at " + settings.QDRANT_URL)
        except Exception:
            # Nếu Docker chưa bật, tự động fallback sang Qdrant Local file storage
            print("[INFO] Docker Qdrant not available. Using local file-based Qdrant storage...")
            local_path = os.path.abspath("./data/qdrant_local")
            os.makedirs(local_path, exist_ok=True)
            self.client = QdrantClient(path=local_path)

        self.embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY or "dummy_key_if_mock"
        )

    def ensure_collection(self):
        """Khởi tạo collection nếu chưa tồn tại"""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
            print(f"[OK] Collection created: {self.collection_name}")

    def ingest_dataset(self, json_file_path: str = "./data/danang_properties.json"):
        """Nạp dữ liệu BĐS vào Qdrant"""
        self.ensure_collection()
        with open(json_file_path, "r", encoding="utf-8") as f:
            properties = json.load(f)

        points = []
        for idx, item in enumerate(properties):
            full_text = f"{item['title']}. {item['description']} Vi tri: {item.get('ward', '')}, {item.get('district', '')}, Da Nang."
            
            if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"):
                vector = self.embeddings.embed_query(full_text)
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
        category: Optional[str] = None,
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
            must_conditions.append(
                FieldCondition(key="price", range=Range(lte=max_price))
            )
        if min_bedrooms:
            must_conditions.append(
                FieldCondition(key="bedrooms", range=Range(gte=min_bedrooms))
            )

        qdrant_filter = Filter(must=must_conditions) if must_conditions else None

        if settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("your_"):
            query_vector = self.embeddings.embed_query(query)
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
