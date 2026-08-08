"""
Real semantic cache using Redis for exact-match and Qdrant for semantic near-hit.
Requires REDIS_URL and QDRANT_URL environment variables.
"""
import hashlib
import json
import logging
import os
from typing import Optional, Dict, Any

from cache.redis_client import get_redis

logger = logging.getLogger(__name__)

COLLECTION_NAME = "inferav22_prompt_cache"
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dim

_encoder = None
_qdrant = None

def _get_encoder():
    global _encoder
    if _encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("SentenceTransformer encoder loaded")
        except ImportError:
            logger.warning("sentence-transformers not installed — semantic cache disabled")
    return _encoder

def _get_qdrant():
    global _qdrant
    if _qdrant is None:
        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            _qdrant = QdrantClient(url=qdrant_url, timeout=5)
            # Ensure collection exists
            try:
                _qdrant.get_collection(COLLECTION_NAME)
            except Exception:
                _qdrant.create_collection(
                    COLLECTION_NAME,
                    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
                )
            logger.info(f"Qdrant client connected to {qdrant_url}")
        except Exception as e:
            logger.warning(f"Qdrant unavailable: {e} — semantic cache will use exact-only mode")
            _qdrant = None
    return _qdrant


class SemanticCacheManager:
    """
    Two-tier prompt caching:
    - Tier 1: Redis exact-match (SHA256 key, 24h TTL)
    - Tier 2: Qdrant semantic near-hit (cosine similarity >= SIMILARITY_THRESHOLD)
    """
    EXACT_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))  # 24h
    SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.95"))

    @classmethod
    def _exact_key(cls, prompt: str, model_url: str) -> str:
        raw = f"{model_url.strip()}:{prompt.strip()}"
        return "cache:exact:" + hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    async def get(cls, prompt: str, model_url: str) -> Optional[str]:
        """Returns cached response or None if cache miss."""
        redis = await get_redis()

        # Tier 1: Exact Redis hit
        key = cls._exact_key(prompt, model_url)
        cached = await redis.get(key)
        if cached:
            await redis.incr("inferav22:stats:cache:exact_hits")
            logger.debug(f"Cache EXACT HIT for key {key[:16]}...")
            return cached

        # Tier 2: Semantic Qdrant hit
        encoder = _get_encoder()
        qdrant = _get_qdrant()
        if encoder and qdrant:
            try:
                from qdrant_client.models import ScoredPoint
                embedding = encoder.encode(prompt).tolist()
                results = qdrant.search(
                    collection_name=COLLECTION_NAME,
                    query_vector=embedding,
                    limit=1,
                    score_threshold=cls.SIMILARITY_THRESHOLD,
                )
                if results:
                    response = results[0].payload.get("response")
                    if response:
                        await redis.incr("inferav22:stats:cache:semantic_hits")
                        logger.debug(f"Cache SEMANTIC HIT (score={results[0].score:.3f})")
                        return response
            except Exception as e:
                logger.warning(f"Qdrant search error: {e}")

        await redis.incr("inferav22:stats:cache:misses")
        return None

    @classmethod
    async def set(cls, prompt: str, model_url: str, response: str) -> None:
        """Store in Redis (exact) and Qdrant (semantic)."""
        redis = await get_redis()

        # Tier 1: Store in Redis
        key = cls._exact_key(prompt, model_url)
        await redis.setex(key, cls.EXACT_TTL_SECONDS, response)

        # Tier 2: Store in Qdrant
        encoder = _get_encoder()
        qdrant = _get_qdrant()
        if encoder and qdrant:
            try:
                from qdrant_client.models import PointStruct
                embedding = encoder.encode(prompt).tolist()
                point_id = abs(hash(key)) % (2 ** 31)
                qdrant.upsert(
                    collection_name=COLLECTION_NAME,
                    points=[PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "prompt": prompt[:1000],
                            "model_url": model_url,
                            "response": response[:4000],
                        }
                    )]
                )
            except Exception as e:
                logger.warning(f"Qdrant upsert error: {e}")

    @classmethod
    async def get_stats(cls) -> Dict[str, Any]:
        """Returns REAL stats from Redis counters."""
        try:
            redis = await get_redis()
            exact_hits = int(await redis.get("inferav22:stats:cache:exact_hits") or 0)
            semantic_hits = int(await redis.get("inferav22:stats:cache:semantic_hits") or 0)
            misses = int(await redis.get("inferav22:stats:cache:misses") or 0)
            total = exact_hits + semantic_hits + misses
            hit_rate = round((exact_hits + semantic_hits) / total * 100, 1) if total > 0 else 0.0

            # Get Redis info for eviction policy
            info = await redis.config_get("maxmemory-policy")
            eviction_policy = info.get("maxmemory-policy", "noeviction")

            return {
                "exact_redis_hits": exact_hits,
                "semantic_qdrant_hits": semantic_hits,
                "cache_misses": misses,
                "total_requests": total,
                "hit_rate_pct": hit_rate,
                "eviction_policy": eviction_policy,
                "similarity_threshold": cls.SIMILARITY_THRESHOLD,
                "ttl_seconds": cls.EXACT_TTL_SECONDS,
                "measured": True,
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "error": str(e),
                "measured": False,
                "message": "Cache stats unavailable — Redis may be disconnected"
            }
