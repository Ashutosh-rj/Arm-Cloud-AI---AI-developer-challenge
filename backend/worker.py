import asyncio
import json
import logging
import os
import sys

# Ensure backend directory is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
)
logger = logging.getLogger("inferav22-worker")

QUEUE_KEY = "inferav22:optimization:queue"
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "4"))

async def process_run(run_id: str):
    """Process a single optimization run."""
    logger.info(f"Processing run {run_id}")
    try:
        # Import here to avoid circular imports
        from cache.redis_client import get_redis
        from db.runs_repository import RunsRepository
        from agents.graph import app_graph

        run = await RunsRepository.get_run(run_id)
        if not run:
            logger.error(f"Run {run_id} not found in DB")
            return

        initial_state = {
            "run_id": run_id,
            "model_url": run["model_url"],
            "target_clouds": run.get("target_clouds", ["graviton4"]),
            "sla_spec": run.get("sla_spec", {}),
            "quality_floor": run.get("quality_floor", 0.98),
            "current_quant_level": "INT4",
            "topology": {},
            "benchmark_results": [],
            "quality_reports": [],
            "optimization_passes": [],
            "errors": [],
            "phase": "planning",
        }

        redis = await get_redis()

        async for output in app_graph.astream(initial_state):
            for node_name, node_state in output.items():
                if node_state:
                    # Persist partial state
                    await RunsRepository.update_run_state(run_id, {
                        "status": "running",
                        "phase": node_state.get("phase", node_name),
                    })
                    # Broadcast to WebSocket subscribers via Redis pub/sub
                    await redis.publish(
                        f"run:{run_id}:events",
                        json.dumps({
                            "event": "node_complete",
                            "node": node_name,
                            "phase": node_state.get("phase", node_name),
                            "run_id": run_id,
                        })
                    )
                    logger.info(f"Run {run_id}: completed node '{node_name}'")

        await RunsRepository.update_run_state(run_id, {"status": "completed"})
        logger.info(f"Run {run_id} completed successfully")

    except Exception as exc:
        logger.exception(f"Run {run_id} failed: {exc}")
        try:
            from db.runs_repository import RunsRepository
            await RunsRepository.update_run_state(run_id, {"status": "failed"})
            redis = await get_redis()
            await redis.publish(
                f"run:{run_id}:events",
                json.dumps({"event": "run_failed", "run_id": run_id, "error": str(exc)})
            )
        except Exception:
            pass

async def main():
    logger.info(f"InferaV22 Worker started | concurrency={WORKER_CONCURRENCY} | queue={QUEUE_KEY}")
    semaphore = asyncio.Semaphore(WORKER_CONCURRENCY)
    tasks: set = set()

    from cache.redis_client import get_redis
    redis = await get_redis()

    while True:
        try:
            # Blocking pop with 5-second timeout
            result = await redis.blpop(QUEUE_KEY, timeout=5)
            if result:
                _, run_id = result
                run_id = run_id.strip()
                logger.info(f"Dequeued run_id={run_id}")

                async def bounded_process(rid=run_id):
                    async with semaphore:
                        await process_run(rid)

                task = asyncio.create_task(bounded_process())
                tasks.add(task)
                task.add_done_callback(tasks.discard)

        except asyncio.CancelledError:
            logger.info("Worker shutting down — cancelling inflight tasks")
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            break
        except Exception as exc:
            logger.error(f"Worker loop error: {exc}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
