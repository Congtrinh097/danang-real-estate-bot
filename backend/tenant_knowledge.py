import hashlib
import json
import math
import re
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from config import settings
from tenant_models import KnowledgeHit


TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
SYNONYMS = {
    "đóng tiền": "thanh toán tiền thuê",
    "hết hợp đồng": "hết hạn gia hạn hợp đồng",
    "rỉ nước": "rò nước vỡ ống",
    "cúp điện": "mất điện",
    "trả phòng": "trả nhà chuyển đi bàn giao",
}


def _tokens(text: str) -> List[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _vector(text: str, size: int = 256) -> List[float]:
    values = [0.0] * size
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % size
        values[index] += 1.0
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


class TenantKnowledgeService:
    """Offline-safe hybrid retrieval: Qdrant dense search + keyword reranking."""

    collection_name = "tenant_support_faq"
    vector_size = 256

    def __init__(self, corpus_path: Path | None = None, qdrant_url: str | None = None):
        self.corpus_path = corpus_path or Path(__file__).parent / "data" / "tenant_faq.json"
        documents = json.loads(self.corpus_path.read_text(encoding="utf-8"))
        self.client = QdrantClient(url=qdrant_url) if qdrant_url else QdrantClient(location=":memory:")
        if not self.client.collection_exists(self.collection_name):
            try:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                )
            except Exception:
                if not self.client.collection_exists(self.collection_name):
                    raise
        if documents:
            points = [
                PointStruct(id=index, vector=_vector(self._searchable_text(document)), payload=document)
                for index, document in enumerate(documents, start=1)
            ]
            self.client.upsert(collection_name=self.collection_name, points=points)

    @staticmethod
    def _searchable_text(document: Dict) -> str:
        return " ".join(
            [document["title"], document["category"], document["content"], *document.get("keywords", [])]
        )

    @staticmethod
    def rewrite_query(query: str) -> str:
        rewritten = query.lower()
        for source, target in SYNONYMS.items():
            if source in rewritten:
                rewritten = f"{rewritten} {target}"
        return rewritten

    def search(self, query: str, limit: int = 3) -> List[KnowledgeHit]:
        rewritten = self.rewrite_query(query)
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=_vector(rewritten),
            limit=max(limit * 2, 4),
            with_payload=True,
        )
        query_tokens = set(_tokens(rewritten))
        reranked = []
        for point in response.points:
            document = point.payload
            if not document:
                continue
            document_tokens = set(_tokens(self._searchable_text(document)))
            keyword_score = len(query_tokens & document_tokens) / max(len(query_tokens), 1)
            hybrid_score = (float(point.score) * 0.65) + (keyword_score * 0.35)
            reranked.append((hybrid_score, document))
        reranked.sort(key=lambda item: item[0], reverse=True)
        return [
            KnowledgeHit(
                id=document["id"],
                title=document["title"],
                category=document["category"],
                content=document["content"],
                score=round(max(0.0, min(score, 1.0)), 4),
            )
            for score, document in reranked[:limit]
        ]

    def index_markdown(self, filename: str, content: str) -> int:
        """Index an uploaded lease/payment policy as paragraph-level knowledge."""
        paragraphs = [
            " ".join(block.split())
            for block in re.split(r"\n\s*\n|(?=^#{1,4}\s)", content, flags=re.MULTILINE)
            if len(" ".join(block.split())) >= 30
        ]
        points = []
        for paragraph in paragraphs:
            point_id = uuid4()
            document = {
                "id": f"uploaded-{point_id.hex}",
                "title": filename,
                "category": "uploaded_policy",
                "keywords": ["hợp đồng", "chính sách", "tenant"],
                "content": paragraph,
            }
            points.append(PointStruct(id=str(point_id), vector=_vector(self._searchable_text(document)), payload=document))
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)


tenant_knowledge_service = TenantKnowledgeService(qdrant_url=settings.TENANT_QDRANT_URL)
