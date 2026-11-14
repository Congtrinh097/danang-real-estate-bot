from typing import List, Dict, Any, Optional
import psycopg2
from config import settings
from ..reporting.cost_summary import cost_reporting_service

class CostAlertEngine:
    """
    Kiểm tra và kích hoạt các cảnh báo vận hành liên quan đến chi phí, ngân sách và tokens.
    """
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.DATABASE_URL

    def _get_connection(self):
        return psycopg2.connect(self.db_url)

    def evaluate_and_record_alerts(self) -> List[Dict[str, Any]]:
        summary = cost_reporting_service.get_daily_cost_summary()
        alerts = []

        # 1. Cảnh báo Chat Workload vượt 80% hoặc 100%
        chat_pct = summary["chat_utilization_pct"]
        if chat_pct >= 100.0:
            alerts.append({
                "alert_type": "BUDGET_EXCEEDED",
                "severity": "CRITICAL",
                "workload_type": "chat",
                "actual_value": summary["chat_spend_vnd"],
                "threshold_value": summary["chat_daily_limit_vnd"],
                "message": f"Hạn mức ngày của Chat đã cạn kiệt: {chat_pct}% ({summary['chat_spend_vnd']:,.0f}/{summary['chat_daily_limit_vnd']:,.0f} VND)"
            })
        elif chat_pct >= 80.0:
            alerts.append({
                "alert_type": "BUDGET_WARNING_80_PCT",
                "severity": "WARNING",
                "workload_type": "chat",
                "actual_value": summary["chat_spend_vnd"],
                "threshold_value": summary["chat_daily_limit_vnd"] * 0.8,
                "message": f"Chi tiêu Chat đã chạm ngưỡng cảnh báo 80%: {chat_pct}%"
            })

        # 2. Cảnh báo Evaluation Workload vượt 80% hoặc 100%
        eval_pct = summary["eval_utilization_pct"]
        if eval_pct >= 100.0:
            alerts.append({
                "alert_type": "BUDGET_EXCEEDED",
                "severity": "CRITICAL",
                "workload_type": "evaluation",
                "actual_value": summary["eval_spend_vnd"],
                "threshold_value": summary["eval_daily_limit_vnd"],
                "message": f"Hạn mức ngày của Evaluation đã cạn kiệt: {eval_pct}%"
            })
        elif eval_pct >= 80.0:
            alerts.append({
                "alert_type": "BUDGET_WARNING_80_PCT",
                "severity": "WARNING",
                "workload_type": "evaluation",
                "actual_value": summary["eval_spend_vnd"],
                "threshold_value": summary["eval_daily_limit_vnd"] * 0.8,
                "message": f"Chi tiêu Evaluation đã chạm ngưỡng cảnh báo 80%: {eval_pct}%"
            })

        # Ghi vào PostgreSQL nếu có cảnh báo phát sinh
        if alerts:
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                for a in alerts:
                    cur.execute("""
                        INSERT INTO agentops_alert_events (
                            alert_type, severity, workload_type, actual_value, threshold_value, message
                        ) VALUES (%s, %s, %s, %s, %s, %s);
                    """, (
                        a["alert_type"], a["severity"], a["workload_type"],
                        a["actual_value"], a["threshold_value"], a["message"]
                    ))
                conn.commit()
            finally:
                cur.close()
                conn.close()

        return alerts

cost_alert_engine = CostAlertEngine()
