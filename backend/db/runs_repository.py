import json
import logging
from typing import Optional, Dict, Any, List
from db.connection import get_pool

logger = logging.getLogger(__name__)


class RunsRepository:

    @staticmethod
    async def create_run(
        run_id: str,
        model_url: str,
        model_hash: str,
        sla_spec: dict,
        target_clouds: List[str],
        quality_floor: float,
        org_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO optimization_runs
                  (id, model_url, model_hash, status, sla_spec, target_clouds,
                   quality_floor, org_id, created_by)
                VALUES ($1, $2, $3, 'queued', $4::jsonb, $5, $6, $7, $8)
                """,
                run_id,
                model_url,
                model_hash,
                json.dumps(sla_spec),
                target_clouds,
                quality_floor,
                org_id,
                user_id,
            )
        logger.info(f"Created run {run_id} in DB")

    @staticmethod
    async def get_run(run_id: str) -> Optional[Dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM optimization_runs WHERE id = $1", run_id
            )
            if row:
                d = dict(row)
                for field in ["sla_spec", "plan", "topology_summary"]:
                    if d.get(field) and isinstance(d[field], str):
                        try:
                            d[field] = json.loads(d[field])
                        except Exception:
                            pass
                return d
            return None

    @staticmethod
    async def update_run_state(run_id: str, updates: Dict[str, Any]) -> None:
        pool = await get_pool()
        status = updates.get("status")
        plan = updates.get("plan")
        async with pool.acquire() as conn:
            if plan:
                await conn.execute(
                    """
                    UPDATE optimization_runs
                    SET status = COALESCE($2, status),
                        plan = COALESCE($3::jsonb, plan),
                        updated_at = now()
                    WHERE id = $1
                    """,
                    run_id,
                    status,
                    json.dumps(plan) if plan else None,
                )
            else:
                await conn.execute(
                    """
                    UPDATE optimization_runs
                    SET status = COALESCE($2, status),
                        updated_at = now()
                    WHERE id = $1
                    """,
                    run_id,
                    status,
                )

    @staticmethod
    async def save_certificate(run_id: str, certificate: Dict[str, Any]) -> None:
        pool = await get_pool()
        cert_id = certificate.get("certificate_id")
        signature = certificate.get("signature", "")
        model_hash = certificate.get("model_hash", "")
        score = certificate.get("score", 0)
        optimal_config = certificate.get("optimal_config", {})
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO certificates
                  (id, run_id, model_hash, optimal_config, score, signature,
                   public_url, payload)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8::jsonb)
                ON CONFLICT (id) DO UPDATE
                  SET optimal_config = EXCLUDED.optimal_config,
                      signature = EXCLUDED.signature,
                      payload = EXCLUDED.payload
                """,
                cert_id,
                run_id,
                model_hash,
                json.dumps(optimal_config),
                score,
                signature,
                certificate.get("public_url", ""),
                json.dumps(certificate),
            )

    @staticmethod
    async def get_certificate(cert_id: str) -> Optional[Dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Try payload column first (full cert), fallback to reconstructing
            row = await conn.fetchrow(
                """SELECT c.*, r.model_url FROM certificates c
                   JOIN optimization_runs r ON r.id = c.run_id
                   WHERE c.id = $1 AND c.expires_at > now()""",
                cert_id,
            )
            if row:
                d = dict(row)
                payload = d.get("payload")
                if payload:
                    if isinstance(payload, str):
                        return json.loads(payload)
                    return dict(payload)
                return d
            return None

    @staticmethod
    async def list_runs(
        org_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            if org_id:
                rows = await conn.fetch(
                    """
                    SELECT id, model_url, status, created_at, updated_at
                    FROM optimization_runs
                    WHERE org_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    org_id,
                    limit,
                    offset,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, model_url, status, created_at, updated_at
                    FROM optimization_runs
                    ORDER BY created_at DESC
                    LIMIT $1 OFFSET $2
                    """,
                    limit,
                    offset,
                )
            return [dict(r) for r in rows]

    @staticmethod
    async def save_benchmark_result(
        run_id: str,
        cloud: str,
        quant_level: str,
        results: Dict[str, Any],
    ) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO benchmark_results
                  (run_id, cloud, quant_level, concurrency,
                   tps_p50, ttft_p50_ms, ttft_p95_ms, ttft_p99_ms,
                   memory_gb, cost_per_1m)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                run_id,
                cloud,
                quant_level,
                results.get("concurrency", 16),
                results.get("tps_p50", 0),
                results.get("ttft_p50_ms", 0),
                results.get("ttft_p95_ms", 0),
                results.get("ttft_p99_ms", 0),
                results.get("memory_gb", 0),
                results.get("cost_per_1m_tokens_usd", 0),
            )
