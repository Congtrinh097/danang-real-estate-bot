"""
backend/due_diligence_service.py
Async Task Manager and SSE Progress Emitter for Deep Real Estate Due Diligence.

Features:
- Dual-store architecture: Redis Hash persistence (24h TTL) + resilient in-memory fallback.
- Redis Pub/Sub event broadcasting with local subscriber queues for zero-drop SSE streaming.
- Monotonic sequence history buffer ensuring late-joining subscribers receive all lifecycle events.
- AgentOps TraceContext integration (workload_type="due_diligence") and wallet cost settlement.
- Fault-tolerant background worker driving LangGraph due_diligence_graph.ainvoke.
"""

import sys
import os
import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union, AsyncGenerator

import redis.asyncio as aioredis

from config import settings
from agentops.monitoring.trace_context import TraceContext
from agentops.cost.user_wallet_service import user_wallet_service
from due_diligence_agent import (
    DueDiligenceRequest,
    DueDiligenceDossier,
    due_diligence_graph,
    DueDiligenceState,
)

logger = logging.getLogger(__name__)


class DueDiligenceTaskManager:
    """Manages asynchronous due diligence task lifecycle, Redis persistence, and SSE progress broadcasting."""

    def __init__(self, redis_url: Optional[str] = "DEFAULT"):
        if redis_url == "DEFAULT":
            self.redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        else:
            self.redis_url = redis_url

        self._in_memory_tasks: Dict[str, Dict[str, Any]] = {}
        self._in_memory_subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self._event_history: Dict[str, List[Dict[str, Any]]] = {}

        self._redis: Optional[aioredis.Redis] = None
        if self.redis_url:
            try:
                self._redis = aioredis.from_url(
                    self.redis_url,
                    socket_connect_timeout=1.0,
                    socket_timeout=2.0,
                    decode_responses=True,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Redis client with URL '{self.redis_url}': {e}. Falling back to in-memory mode.")
                self._redis = None

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def submit_task(
        self,
        req: Union[DueDiligenceRequest, Dict[str, Any]],
        user_id: Optional[str] = None,
    ) -> str:
        task_id = f"dd_task_{uuid.uuid4().hex[:12]}"
        now = self._now_iso()

        if isinstance(req, dict):
            req_dict = dict(req)
            effective_user_id = user_id or req_dict.get("user_id") or "default_user"
        else:
            req_dict = req.model_dump() if hasattr(req, "model_dump") else dict(req)
            effective_user_id = user_id or getattr(req, "user_id", None) or "default_user"

        TraceContext.set_context(
            request_id=task_id,
            thread_id=f"thread_{task_id}",
            workload_type="due_diligence",
        )

        initial_event = {
            "type": "progress",
            "task_id": task_id,
            "status": "pending",
            "stage": "pending",
            "progress": 0,
            "seq": 0,
            "timestamp": now,
        }

        task_record: Dict[str, Any] = {
            "task_id": task_id,
            "status": "pending",
            "stage": "pending",
            "progress": 0,
            "request": req_dict,
            "dossier": None,
            "result": None,
            "error_message": None,
            "created_at": now,
            "updated_at": now,
            "events": [initial_event],
            "user_id": str(effective_user_id),
        }

        self._in_memory_tasks[task_id] = task_record
        self._event_history[task_id] = [initial_event]
        self._in_memory_subscribers[task_id] = []

        if self._redis is not None:
            try:
                key = f"due_diligence:{task_id}"
                hash_mapping = {
                    "task_id": task_id,
                    "status": "pending",
                    "stage": "pending",
                    "progress": "0",
                    "request": json.dumps(req_dict, ensure_ascii=False),
                    "dossier": "",
                    "error_message": "",
                    "created_at": now,
                    "updated_at": now,
                    "events": json.dumps([initial_event], ensure_ascii=False),
                    "user_id": str(effective_user_id),
                }
                await self._redis.hset(key, mapping=hash_mapping)
                await self._redis.expire(key, 86400)
            except Exception as e:
                logger.warning(f"Redis write error on submit_task for {task_id}: {e}")

        bg_task = asyncio.create_task(self._execute_task_workflow(task_id, req, effective_user_id))
        self._background_tasks[task_id] = bg_task
        bg_task.add_done_callback(lambda _: self._background_tasks.pop(task_id, None))

        return task_id

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        mem_task = self._in_memory_tasks.get(task_id)

        if self._redis is not None:
            try:
                key = f"due_diligence:{task_id}"
                raw = await self._redis.hgetall(key)
                if raw:
                    req_val = json.loads(raw["request"]) if raw.get("request") else None
                    dossier_val = json.loads(raw["dossier"]) if raw.get("dossier") else None
                    events_val = json.loads(raw["events"]) if raw.get("events") else []
                    redis_task = {
                        "task_id": raw.get("task_id", task_id),
                        "status": raw.get("status", "pending"),
                        "stage": raw.get("stage", raw.get("status", "pending")),
                        "progress": int(raw.get("progress", 0)),
                        "request": req_val,
                        "dossier": dossier_val,
                        "result": dossier_val,
                        "error_message": raw.get("error_message") or None,
                        "created_at": raw.get("created_at"),
                        "updated_at": raw.get("updated_at"),
                        "events": events_val,
                        "user_id": raw.get("user_id"),
                    }
                    if mem_task:
                        if mem_task.get("progress", 0) >= redis_task.get("progress", 0):
                            return dict(mem_task)
                    return redis_task
            except Exception as e:
                logger.warning(f"Redis read error on get_task_status for {task_id}: {e}")

        if mem_task:
            return dict(mem_task)
        return None

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        stage: Optional[str] = None,
        progress: Optional[int] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        stage_val = stage or status
        prog_val = progress if progress is not None else 0
        now = self._now_iso()

        task = self._in_memory_tasks.setdefault(task_id, {
            "task_id": task_id,
            "created_at": now,
            "events": [],
        })

        # Terminal state protection: once completed or failed, do not regress to non-terminal
        if task.get("status") in ["completed", "failed"] and status not in ["completed", "failed"]:
            return

        # Monotonic progress protection: do not allow progress to regress to a lower value (unless failing)
        if task.get("progress", 0) > prog_val and status not in ["failed"]:
            return
        task["status"] = status
        task["stage"] = stage_val
        task["progress"] = prog_val
        task["updated_at"] = now
        if result is not None:
            task["dossier"] = result
            task["result"] = result
        if error is not None:
            task["error_message"] = error

        events = self._event_history.setdefault(task_id, [])
        seq = len(events)
        event_type = "completed" if status == "completed" else ("error" if status == "failed" else "progress")
        event_payload = {
            "type": event_type,
            "task_id": task_id,
            "status": status,
            "stage": stage_val,
            "progress": prog_val,
            "seq": seq,
            "timestamp": now,
        }
        if result is not None:
            event_payload["dossier"] = result
            event_payload["result"] = result
        if error is not None:
            event_payload["error"] = error

        events.append(event_payload)
        task["events"] = events

        await self.publish_event(task_id, event_payload)

        if self._redis is not None:
            try:
                key = f"due_diligence:{task_id}"
                mapping = {
                    "status": status,
                    "stage": stage_val,
                    "progress": str(prog_val),
                    "updated_at": now,
                    "events": json.dumps(events, ensure_ascii=False),
                }
                if result is not None:
                    mapping["dossier"] = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
                if error is not None:
                    mapping["error_message"] = str(error)

                await self._redis.hset(key, mapping=mapping)
                await self._redis.expire(key, 86400)
            except Exception as e:
                logger.warning(f"Redis update error on update_task_status for {task_id}: {e}")

    async def update_task_stage(
        self,
        task_id: str,
        stage: str,
        progress: int,
        message: Optional[str] = None,
    ) -> None:
        await self.update_task_status(task_id, status=stage, stage=stage, progress=progress)

    async def publish_event(self, task_id: str, payload: Dict[str, Any]) -> None:
        subscribers = list(self._in_memory_subscribers.get(task_id, []))
        for q in subscribers:
            try:
                q.put_nowait(payload)
            except Exception as e:
                logger.debug(f"Queue delivery failed for task {task_id}: {e}")

        if self._redis is not None:
            try:
                channel = f"due_diligence_events:{task_id}"
                await self._redis.publish(channel, json.dumps(payload, ensure_ascii=False))
            except Exception as e:
                logger.warning(f"Redis publish error on channel due_diligence_events:{task_id}: {e}")

    async def stream_progress(self, task_id: str) -> AsyncGenerator[str, None]:
        status_info = await self.get_task_status(task_id)
        if status_info is None:
            error_payload = {
                "type": "error",
                "task_id": task_id,
                "error": f"Task {task_id} not found",
                "status": "not_found",
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        history = list(self._event_history.get(task_id, []))
        if not history and status_info.get("events"):
            history = list(status_info["events"])

        last_seq = -1
        is_terminal = False
        for ev in history:
            seq = ev.get("seq", last_seq + 1)
            if seq > last_seq:
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                last_seq = seq
            if ev.get("stage") == "completed" or ev.get("status") in ["completed", "failed"]:
                is_terminal = True

        if is_terminal or status_info.get("status") in ["completed", "failed"]:
            yield "data: [DONE]\n\n"
            return

        queue: asyncio.Queue = asyncio.Queue()
        if task_id not in self._in_memory_subscribers:
            self._in_memory_subscribers[task_id] = []
        self._in_memory_subscribers[task_id].append(queue)

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    curr = await self.get_task_status(task_id)
                    if curr and curr.get("status") in ["completed", "failed"]:
                        yield "data: [DONE]\n\n"
                        break
                    continue

                seq = event.get("seq", last_seq + 1)
                if seq > last_seq:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    last_seq = seq

                if event.get("stage") == "completed" or event.get("status") in ["completed", "failed"]:
                    yield "data: [DONE]\n\n"
                    break
        finally:
            if task_id in self._in_memory_subscribers:
                if queue in self._in_memory_subscribers[task_id]:
                    self._in_memory_subscribers[task_id].remove(queue)
                if not self._in_memory_subscribers[task_id]:
                    del self._in_memory_subscribers[task_id]

    async def _execute_task_workflow(
        self,
        task_id: str,
        req: Union[DueDiligenceRequest, Dict[str, Any]],
        user_id: Optional[str] = None,
    ) -> None:
        effective_user_id = user_id or "default_user"
        TraceContext.set_context(
            request_id=task_id,
            thread_id=f"thread_{task_id}",
            workload_type="due_diligence",
        )

        try:
            if self._in_memory_tasks.get(task_id, {}).get("status") in ["completed", "failed"]:
                return
            await self.update_task_status(task_id, status="planning", stage="planning", progress=15)
            await asyncio.sleep(0.01)

            if self._in_memory_tasks.get(task_id, {}).get("status") in ["completed", "failed"]:
                return
            await self.update_task_status(task_id, status="investigating", stage="investigating", progress=50)
            await asyncio.sleep(0.01)

            req_obj = req if isinstance(req, DueDiligenceRequest) else DueDiligenceRequest(**req)
            initial_state = {
                **req_obj.model_dump(),
                "request": req_obj,
                "stage": "planning",
                "progress": 15,
                "user_id": effective_user_id,
            }

            if self._in_memory_tasks.get(task_id, {}).get("status") in ["completed", "failed"]:
                return
            final_state = await due_diligence_graph.ainvoke(initial_state)

            if self._in_memory_tasks.get(task_id, {}).get("status") in ["completed", "failed"]:
                return
            await self.update_task_status(task_id, status="critiquing", stage="critiquing", progress=75)
            await asyncio.sleep(0.01)

            if self._in_memory_tasks.get(task_id, {}).get("status") in ["completed", "failed"]:
                return
            await self.update_task_status(task_id, status="synthesizing", stage="synthesizing", progress=90)
            await asyncio.sleep(0.01)

            dossier = final_state.get("dossier")
            if hasattr(dossier, "model_dump"):
                dossier_data = dossier.model_dump()
            elif isinstance(dossier, dict):
                dossier_data = dossier
            else:
                dossier_data = None

            await self.update_task_status(
                task_id,
                status="completed",
                stage="completed",
                progress=100,
                result=dossier_data,
            )
        except Exception as e:
            logger.exception(f"Error in due diligence execution for task {task_id}: {e}")
            await self.update_task_status(
                task_id,
                status="failed",
                stage="failed",
                progress=100,
                error=str(e),
            )
        finally:
            try:
                user_wallet_service.deduct_request_cost(
                    user_id=effective_user_id,
                    request_id=task_id,
                )
            except Exception as w_err:
                logger.warning(f"Wallet deduction failed for task {task_id}: {w_err}")

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None


due_diligence_task_manager = DueDiligenceTaskManager()
