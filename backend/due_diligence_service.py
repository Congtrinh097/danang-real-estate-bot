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

import psycopg2
from psycopg2.extras import RealDictCursor
import redis.asyncio as aioredis

from config import settings
from agentops import AgentOpsCallbackHandler, langfuse_manager
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
    """Manages asynchronous due diligence task lifecycle, PostgreSQL persistence, Redis PubSub, and SSE progress broadcasting."""

    def __init__(self, redis_url: Optional[str] = "DEFAULT", db_url: Optional[str] = None):
        if redis_url == "DEFAULT":
            self.redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        else:
            self.redis_url = redis_url

        self.db_url = db_url or getattr(settings, "DATABASE_URL", "postgresql://admin:danang_realestate_secret@localhost:5435/danang_real_estate")

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

        self.init_db()

    def _get_db_connection(self):
        return psycopg2.connect(self.db_url)

    def init_db(self):
        """Khởi tạo bảng due_diligence_records và due_diligence_settings trong PostgreSQL"""
        create_tables_sql = """
        CREATE TABLE IF NOT EXISTS due_diligence_records (
            id SERIAL PRIMARY KEY,
            task_id VARCHAR(64) UNIQUE NOT NULL,
            property_id VARCHAR(64),
            property_title TEXT NOT NULL,
            property_price NUMERIC(15, 2) NOT NULL,
            area_m2 NUMERIC(10, 2) NOT NULL,
            district VARCHAR(64) NOT NULL,
            ward VARCHAR(64),
            investment_objective VARCHAR(32) DEFAULT 'residential',
            equity_ratio NUMERIC(5, 2) DEFAULT 0.7,
            equity_capital_vnd NUMERIC(15, 2),
            loan_amount_vnd NUMERIC(15, 2),
            user_id VARCHAR(64) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'completed',
            verdict VARCHAR(64),
            overall_score NUMERIC(5, 2),
            request_data JSONB NOT NULL,
            dossier_data JSONB NOT NULL,
            is_cached BOOLEAN DEFAULT FALSE,
            cached_from_task_id VARCHAR(64),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_dd_property_id ON due_diligence_records(property_id);
        CREATE INDEX IF NOT EXISTS idx_dd_user_id ON due_diligence_records(user_id);
        CREATE INDEX IF NOT EXISTS idx_dd_lookup ON due_diligence_records(district, property_title, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_dd_created_at ON due_diligence_records(created_at DESC);

        CREATE TABLE IF NOT EXISTS due_diligence_settings (
            setting_key VARCHAR(64) PRIMARY KEY,
            setting_value JSONB NOT NULL,
            description TEXT,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO due_diligence_settings (setting_key, setting_value, description)
        VALUES 
            ('cache_config', '{"cache_enabled": true, "cache_ttl_hours": 48, "cache_hit_cost_vnd": 0.0, "allow_force_refresh": true}', 'Cấu hình thời gian và chi phí Cache thẩm định')
        ON CONFLICT (setting_key) DO NOTHING;
        """
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(create_tables_sql)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize due diligence PostgreSQL tables: {e}")

    def get_settings(self) -> Dict[str, Any]:
        """Lấy cài đặt Admin cho phân hệ Thẩm định & Cache từ PostgreSQL"""
        default_settings = {
            "cache_enabled": True,
            "cache_ttl_hours": 48,
            "cache_hit_cost_vnd": 0.0,
            "allow_force_refresh": True,
        }
        try:
            with self._get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT setting_value FROM due_diligence_settings WHERE setting_key = 'cache_config'")
                    row = cur.fetchone()
                    if row and row.get("setting_value"):
                        val = row["setting_value"]
                        if isinstance(val, str):
                            val = json.loads(val)
                        default_settings.update(val)
        except Exception as e:
            logger.warning(f"Error fetching due diligence settings from DB: {e}")
        return default_settings

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Cập nhật cài đặt Admin cho phân hệ Thẩm định & Cache vào PostgreSQL"""
        current = self.get_settings()
        current.update(updates)
        try:
            with self._get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        INSERT INTO due_diligence_settings (setting_key, setting_value, updated_at)
                        VALUES ('cache_config', %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (setting_key) DO UPDATE SET
                            setting_value = EXCLUDED.setting_value,
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING setting_value;
                    """, (json.dumps(current),))
                    row = cur.fetchone()
                    conn.commit()
                    if row and row.get("setting_value"):
                        val = row["setting_value"]
                        if isinstance(val, str):
                            val = json.loads(val)
                        return val
        except Exception as e:
            logger.error(f"Error updating due diligence settings: {e}")
        return current

    def save_dossier_record(
        self,
        task_id: str,
        user_id: str,
        request_data: Dict[str, Any],
        dossier_data: Dict[str, Any],
        is_cached: bool = False,
        cached_from_task_id: Optional[str] = None
    ) -> bool:
        """Lưu trữ hồ sơ thẩm định bền vững vào PostgreSQL"""
        prop_id = request_data.get("property_id")
        title = request_data.get("property_title", "Bất động sản Đà Nẵng")
        price = float(request_data.get("property_price", 0.0) or 0.0)
        area = float(request_data.get("area_m2", 0.0) or 0.0)
        district = request_data.get("district", "Đà Nẵng")
        ward = request_data.get("ward")
        obj = request_data.get("investment_objective", "residential")
        ratio = float(request_data.get("equity_ratio", 0.7) or 0.7)
        capital = request_data.get("equity_capital_vnd")
        loan = request_data.get("loan_amount_vnd")

        verdict = dossier_data.get("verdict")
        score = dossier_data.get("overall_score")
        if score is not None:
            try:
                score = float(score)
            except Exception:
                score = None

        insert_sql = """
        INSERT INTO due_diligence_records (
            task_id, property_id, property_title, property_price, area_m2,
            district, ward, investment_objective, equity_ratio, equity_capital_vnd,
            loan_amount_vnd, user_id, status, verdict, overall_score,
            request_data, dossier_data, is_cached, cached_from_task_id, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, 'completed', %s, %s,
            %s, %s, %s, %s, CURRENT_TIMESTAMP
        )
        ON CONFLICT (task_id) DO UPDATE SET
            status = EXCLUDED.status,
            verdict = EXCLUDED.verdict,
            overall_score = EXCLUDED.overall_score,
            dossier_data = EXCLUDED.dossier_data,
            updated_at = CURRENT_TIMESTAMP;
        """
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(insert_sql, (
                        task_id, prop_id, title, price, area,
                        district, ward, obj, ratio, capital,
                        loan, str(user_id), verdict, score,
                        json.dumps(request_data, ensure_ascii=False),
                        json.dumps(dossier_data, ensure_ascii=False),
                        is_cached, cached_from_task_id
                    ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving dossier record to DB for task {task_id}: {e}")
            return False

    def find_cached_dossier(self, req_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Tìm kiếm hồ sơ thẩm định hợp lệ còn hiệu lực trong bộ nhớ Cache.
        1. Kiểm tra cache_enabled và cache_ttl_hours từ settings.
        2. Nếu có property_id -> tìm theo property_id.
        3. Nếu không có property_id -> tìm theo LOWER(TRIM(property_title)) và district.
        """
        settings = self.get_settings()
        if not settings.get("cache_enabled", True):
            return None

        ttl_hours = int(settings.get("cache_ttl_hours", 48) or 48)
        prop_id = req_data.get("property_id")
        title = (req_data.get("property_title") or "").strip().lower()
        district = (req_data.get("district") or "").strip()
        area = req_data.get("area_m2")

        try:
            with self._get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if prop_id:
                        cur.execute("""
                            SELECT * FROM due_diligence_records
                            WHERE property_id = %s
                              AND status = 'completed'
                              AND created_at >= NOW() - (%s || ' HOURS')::INTERVAL
                            ORDER BY created_at DESC
                            LIMIT 1;
                        """, (str(prop_id), ttl_hours))
                        row = cur.fetchone()
                        if row:
                            return self._format_db_record(row)
                        return None

                    if title and district:
                        query = """
                            SELECT * FROM due_diligence_records
                            WHERE LOWER(TRIM(property_title)) = %s
                              AND district = %s
                              AND status = 'completed'
                              AND created_at >= NOW() - (%s || ' HOURS')::INTERVAL
                        """
                        params = [title, district, ttl_hours]
                        if area is not None:
                            try:
                                a_float = float(area)
                                query += " AND ABS(area_m2 - %s) <= 1.0"
                                params.append(a_float)
                            except Exception:
                                pass
                        query += " ORDER BY created_at DESC LIMIT 1;"
                        cur.execute(query, tuple(params))
                        row = cur.fetchone()
                        if row:
                            return self._format_db_record(row)
        except Exception as e:
            logger.warning(f"Error querying cached dossier: {e}")
        return None

    def _format_db_record(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Chuẩn hóa dữ liệu trả về từ PostgreSQL record"""
        record = dict(row)
        if isinstance(record.get("request_data"), str):
            record["request_data"] = json.loads(record["request_data"])
        if isinstance(record.get("dossier_data"), str):
            record["dossier_data"] = json.loads(record["dossier_data"])
        if record.get("created_at") and hasattr(record["created_at"], "isoformat"):
            record["created_at"] = record["created_at"].isoformat()
        if record.get("updated_at") and hasattr(record["updated_at"], "isoformat"):
            record["updated_at"] = record["updated_at"].isoformat()
        if record.get("property_price") is not None:
            record["property_price"] = float(record["property_price"])
        if record.get("area_m2") is not None:
            record["area_m2"] = float(record["area_m2"])
        if record.get("equity_ratio") is not None:
            record["equity_ratio"] = float(record["equity_ratio"])
        if record.get("overall_score") is not None:
            record["overall_score"] = float(record["overall_score"])
        return record

    def clear_cache(self, property_id: Optional[str] = None) -> int:
        """Dọn dẹp cache: đánh dấu status='invalidated' để buộc phân tích mới"""
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cur:
                    if property_id:
                        cur.execute("""
                            UPDATE due_diligence_records
                            SET status = 'invalidated', updated_at = CURRENT_TIMESTAMP
                            WHERE property_id = %s AND status = 'completed';
                        """, (str(property_id),))
                    else:
                        cur.execute("""
                            UPDATE due_diligence_records
                            SET status = 'invalidated', updated_at = CURRENT_TIMESTAMP
                            WHERE status = 'completed';
                        """)
                    count = cur.rowcount
                    conn.commit()
                    return count
        except Exception as e:
            logger.error(f"Error clearing due diligence cache: {e}")
            return 0

    def get_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        scope: str = "user"
    ) -> List[Dict[str, Any]]:
        """Lấy danh sách lịch sử thẩm định từ PostgreSQL"""
        try:
            with self._get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if scope == "user" and user_id:
                        cur.execute("""
                            SELECT id, task_id, property_id, property_title, property_price, area_m2,
                                   district, ward, investment_objective, equity_ratio, user_id,
                                   status, verdict, overall_score, is_cached, cached_from_task_id, created_at
                            FROM due_diligence_records
                            WHERE user_id = %s
                            ORDER BY created_at DESC
                            LIMIT %s OFFSET %s;
                        """, (user_id, limit, offset))
                    else:
                        cur.execute("""
                            SELECT id, task_id, property_id, property_title, property_price, area_m2,
                                   district, ward, investment_objective, equity_ratio, user_id,
                                   status, verdict, overall_score, is_cached, cached_from_task_id, created_at
                            FROM due_diligence_records
                            ORDER BY created_at DESC
                            LIMIT %s OFFSET %s;
                        """, (limit, offset))
                    rows = cur.fetchall()
                    result = []
                    for r in rows:
                        item = dict(r)
                        if item.get("created_at") and hasattr(item["created_at"], "isoformat"):
                            item["created_at"] = item["created_at"].isoformat()
                        if item.get("property_price") is not None:
                            item["property_price"] = float(item["property_price"])
                        if item.get("area_m2") is not None:
                            item["area_m2"] = float(item["area_m2"])
                        if item.get("equity_ratio") is not None:
                            item["equity_ratio"] = float(item["equity_ratio"])
                        if item.get("overall_score") is not None:
                            item["overall_score"] = float(item["overall_score"])
                        result.append(item)
                    return result
        except Exception as e:
            logger.error(f"Error fetching due diligence history: {e}")
            return []

    def get_dossier_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết đầy đủ hồ sơ thẩm định theo task_id"""
        try:
            with self._get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM due_diligence_records WHERE task_id = %s", (task_id,))
                    row = cur.fetchone()
                    if row:
                        return self._format_db_record(row)
        except Exception as e:
            logger.error(f"Error fetching dossier by task_id {task_id}: {e}")
        return None

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

        # Kiểm tra Cache trước khi chạy workflow tốn kém
        cached_record = self.find_cached_dossier(req_dict)
        if cached_record and cached_record.get("dossier_data"):
            cached_dossier = cached_record["dossier_data"]
            cached_from = cached_record.get("task_id")
            logger.info(f"Cache HIT for due diligence request! Reusing dossier from task {cached_from}")

            # Lưu bản ghi mới cho user này đánh dấu is_cached=True
            self.save_dossier_record(
                task_id=task_id,
                user_id=str(effective_user_id),
                request_data=req_dict,
                dossier_data=cached_dossier,
                is_cached=True,
                cached_from_task_id=cached_from
            )

            completed_event = {
                "type": "completed",
                "task_id": task_id,
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "seq": 1,
                "timestamp": now,
                "dossier": cached_dossier,
                "result": cached_dossier,
                "is_cached": True,
                "cached_from_task_id": cached_from
            }
            task_record.update({
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "dossier": cached_dossier,
                "result": cached_dossier,
                "is_cached": True,
                "cached_from_task_id": cached_from,
                "updated_at": now,
                "events": [initial_event, completed_event]
            })
            self._in_memory_tasks[task_id] = task_record
            self._event_history[task_id] = [initial_event, completed_event]
            self._in_memory_subscribers[task_id] = []

            if self._redis is not None:
                try:
                    key = f"due_diligence:{task_id}"
                    await self._redis.hset(key, mapping={
                        "task_id": task_id,
                        "status": "completed",
                        "stage": "completed",
                        "progress": "100",
                        "request": json.dumps(req_dict, ensure_ascii=False),
                        "dossier": json.dumps(cached_dossier, ensure_ascii=False),
                        "error_message": "",
                        "created_at": now,
                        "updated_at": now,
                        "is_cached": "true",
                        "cached_from_task_id": str(cached_from or ""),
                        "events": json.dumps([initial_event, completed_event], ensure_ascii=False),
                        "user_id": str(effective_user_id),
                    })
                    await self._redis.expire(key, 86400)
                except Exception as re_err:
                    logger.warning(f"Redis write error on cached task {task_id}: {re_err}")

            return task_id

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
                    # Keep-alive heartbeat comment for SSE connection stability
                    yield ": ping\n\n"
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

        lf_cb = None
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

            callbacks = [AgentOpsCallbackHandler(agent_name="DueDiligenceAgent")]
            lf_cb = langfuse_manager.get_callback_handler(
                request_id=task_id,
                thread_id=f"thread_{task_id}",
                user_id=effective_user_id,
                tags=["due_diligence", "danang_real_estate"],
            )
            if lf_cb:
                callbacks.append(lf_cb)

            config = {
                "configurable": {"thread_id": f"thread_{task_id}"},
                "callbacks": callbacks,
                "metadata": {
                    "thread_id": f"thread_{task_id}",
                    "request_id": task_id,
                    "task_id": task_id,
                    "user_id": effective_user_id,
                    "workload_type": "due_diligence",
                    "session_type": "due_diligence",
                },
                "tags": ["due_diligence", f"user_{effective_user_id}", getattr(req_obj, "district", "DaNang")],
                "run_name": f"DueDiligenceGraph-{task_id}",
            }

            try:
                final_state = await due_diligence_graph.ainvoke(initial_state, config=config)
            except TypeError as te:
                if "config" in str(te):
                    final_state = await due_diligence_graph.ainvoke(initial_state)
                else:
                    raise

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

            if dossier_data:
                try:
                    req_dict = req if isinstance(req, dict) else (req.model_dump() if hasattr(req, "model_dump") else dict(req))
                    self.save_dossier_record(
                        task_id=task_id,
                        user_id=effective_user_id,
                        request_data=req_dict,
                        dossier_data=dossier_data,
                        is_cached=False
                    )
                except Exception as db_err:
                    logger.warning(f"Failed to persist dossier record to DB for task {task_id}: {db_err}")
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
            if lf_cb and hasattr(lf_cb, "_langfuse_client") and hasattr(lf_cb._langfuse_client, "flush"):
                try:
                    lf_cb._langfuse_client.flush()
                except Exception as f_err:
                    logger.warning(f"Failed to flush Langfuse client: {f_err}")
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
