import React, { useState, useEffect, useCallback } from "react";
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  Cpu,
  Layers,
  MessageSquare,
  Clock,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Settings,
  X,
  ShieldAlert,
  Activity,
  Calendar,
  Zap,
  ChevronRight
} from "lucide-react";

export default function AgentOpsAdmin({ API_BASE = "" }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Dữ liệu báo cáo
  const [summary, setSummary] = useState(null);
  const [models, setModels] = useState([]);
  const [workloads, setWorkloads] = useState([]);
  const [threads, setThreads] = useState([]);
  const [recentEvents, setRecentEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [budgets, setBudgets] = useState([]);

  // Sub-view tab trong AgentOps: "models" | "workloads" | "threads" | "recent" | "alerts" | "budgets"
  const [subView, setSubView] = useState("models");

  // State Modal Cấu hình Ngân Sách
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [editingBudget, setEditingBudget] = useState({
    workload_type: "chat",
    turn_limit_vnd: 5000,
    thread_limit_vnd: 20000,
    daily_limit_vnd: 200000
  });
  const [savingBudget, setSavingBudget] = useState(false);
  const [modalFeedback, setModalFeedback] = useState(null);

  // Formatters
  const formatVND = (num) => {
    if (num === null || num === undefined) return "0 ₫";
    return Math.round(Number(num)).toLocaleString("vi-VN") + " ₫";
  };

  const formatVNDDecimal = (num) => {
    if (num === null || num === undefined) return "0 ₫";
    return Number(num).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + " ₫";
  };

  const formatUSD = (num) => {
    if (num === null || num === undefined) return "$0.00";
    return "$" + Number(num).toFixed(4);
  };

  const formatNum = (num) => {
    if (num === null || num === undefined) return "0";
    return Number(num).toLocaleString("vi-VN");
  };

  const formatDate = (iso) => {
    if (!iso) return "-";
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) + 
        " " + d.toLocaleDateString("vi-VN");
    } catch {
      return iso;
    }
  };

  // Tải dữ liệu toàn bộ AgentOps
  const loadAgentOpsData = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const [
        summaryRes,
        modelsRes,
        workloadsRes,
        threadsRes,
        recentRes,
        alertsRes,
        budgetsRes
      ] = await Promise.all([
        fetch(`${API_BASE}/api/agentops/reports/summary`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/api/agentops/reports/model`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/agentops/reports/workload`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/agentops/reports/thread?limit=25`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/agentops/reports/recent-events?limit=25`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/agentops/alerts/history?limit=25`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/agentops/budgets`).then(r => r.json()).catch(() => ({ budgets: [] }))
      ]);

      if (summaryRes) setSummary(summaryRes);
      if (Array.isArray(modelsRes)) setModels(modelsRes);
      if (Array.isArray(workloadsRes)) setWorkloads(workloadsRes);
      if (Array.isArray(threadsRes)) setThreads(threadsRes);
      if (Array.isArray(recentRes)) setRecentEvents(recentRes);
      if (Array.isArray(alertsRes)) setAlerts(alertsRes);
      if (budgetsRes && Array.isArray(budgetsRes.budgets)) setBudgets(budgetsRes.budgets);
    } catch (err) {
      console.error("Lỗi nạp dữ liệu AgentOps:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [API_BASE]);

  useEffect(() => {
    loadAgentOpsData();
  }, [loadAgentOpsData]);

  // Auto-refresh mỗi 30s nếu được kích hoạt
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadAgentOpsData(true);
    }, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadAgentOpsData]);

  // Mở modal cấu hình cho workload cụ thể
  const handleOpenBudgetModal = (budgetRow = null) => {
    if (budgetRow) {
      setEditingBudget({
        workload_type: budgetRow.workload_type || "chat",
        turn_limit_vnd: budgetRow.turn_limit_vnd || 5000,
        thread_limit_vnd: budgetRow.thread_limit_vnd || 20000,
        daily_limit_vnd: budgetRow.daily_limit_vnd || 200000
      });
    } else {
      setEditingBudget({
        workload_type: "chat",
        turn_limit_vnd: 5000,
        thread_limit_vnd: 20000,
        daily_limit_vnd: 200000
      });
    }
    setModalFeedback(null);
    setShowBudgetModal(true);
  };

  // Submit cập nhật hạn mức ngân sách
  const handleSaveBudget = async (e) => {
    e.preventDefault();
    setSavingBudget(true);
    setModalFeedback(null);

    try {
      const res = await fetch(`${API_BASE}/api/agentops/budgets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workload_type: editingBudget.workload_type,
          turn_limit_vnd: Number(editingBudget.turn_limit_vnd),
          thread_limit_vnd: Number(editingBudget.thread_limit_vnd),
          daily_limit_vnd: Number(editingBudget.daily_limit_vnd)
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setModalFeedback({ type: "success", message: `Đã cập nhật hạn mức cho "${editingBudget.workload_type}" thành công!` });
        setTimeout(() => {
          setShowBudgetModal(false);
          loadAgentOpsData(true);
        }, 1200);
      } else {
        setModalFeedback({ type: "error", message: data.detail || "Cập nhật thất bại. Vui lòng thử lại!" });
      }
    } catch (err) {
      setModalFeedback({ type: "error", message: "Lỗi kết nối: " + err.message });
    } finally {
      setSavingBudget(false);
    }
  };

  const getUtilizationColor = (pct) => {
    if (pct >= 100) return "#ef4444"; // Đỏ
    if (pct >= 80) return "#f59e0b";  // Vàng cam
    return "#10b981";                 // Xanh lá
  };

  return (
    <div className="agentops-admin-root">
      {/* Top Banner Actions & Title */}
      <div className="agentops-top-header">
        <div>
          <h3 className="agentops-heading">
            <Activity className="icon-pulse" size={20} color="#2563eb" />
            Bảng Điều Khiển Chi Phí & Giám Sát AgentOps
          </h3>
          <p className="agentops-subheading">
            Theo dõi chi tiêu LLM, mức tiêu thụ Tokens, hiệu năng mô hình AI và kiểm soát ngân sách theo thời gian thực.
          </p>
        </div>

        <div className="agentops-action-bar">
          <label className="auto-refresh-toggle" title="Tự động cập nhật số liệu mỗi 30 giây">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            <span>Auto 30s</span>
          </label>

          <button
            className="btn-agentops-secondary"
            onClick={() => loadAgentOpsData(false)}
            disabled={refreshing}
            title="Tải lại toàn bộ số liệu"
          >
            <RefreshCw size={15} className={refreshing ? "spin-icon" : ""} />
            <span>Làm mới</span>
          </button>

          <button
            className="btn-agentops-primary"
            onClick={() => handleOpenBudgetModal(null)}
            title="Mở bảng thiết lập hạn mức chi tiêu"
          >
            <Settings size={15} />
            <span>Cấu Hình Ngân Sách</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="agentops-kpi-grid">
        {/* Card 1: Tổng chi phí hôm nay */}
        <div className="agentops-kpi-card highlight-blue">
          <div className="kpi-icon-badge blue">
            <DollarSign size={20} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Tổng Chi Phí Hôm Nay</span>
            <div className="kpi-main-val">
              {formatVND(summary?.total_daily_spend_vnd)}
            </div>
            <span className="kpi-sub-val">
              {formatNum(summary?.total_calls_today)} cuộc gọi LLM đã ghi nhận
            </span>
          </div>
        </div>

        {/* Card 2: Chi tiêu Chat Workload */}
        <div className="agentops-kpi-card">
          <div className="kpi-icon-badge green">
            <MessageSquare size={20} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Chi Tiêu Chat (Tư Vấn BĐS)</span>
            <div className="kpi-main-val">
              {formatVND(summary?.chat_spend_vnd)}
            </div>
            <div className="kpi-meta-row">
              <span className="kpi-sub-val">
                Hạn mức: {formatVND(summary?.chat_daily_limit_vnd)}
              </span>
              <span
                className="badge-kpi-pct"
                style={{
                  background: (summary?.chat_utilization_pct || 0) >= 80 ? "#fee2e2" : "#ecfdf5",
                  color: getUtilizationColor(summary?.chat_utilization_pct || 0)
                }}
              >
                {summary?.chat_utilization_pct || 0}%
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Chi tiêu Evaluation Workload */}
        <div className="agentops-kpi-card">
          <div className="kpi-icon-badge purple">
            <TrendingUp size={20} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Chi Tiêu Đánh Giá (Eval/RAG)</span>
            <div className="kpi-main-val">
              {formatVND(summary?.eval_spend_vnd)}
            </div>
            <div className="kpi-meta-row">
              <span className="kpi-sub-val">
                Hạn mức: {formatVND(summary?.eval_daily_limit_vnd)}
              </span>
              <span
                className="badge-kpi-pct"
                style={{
                  background: (summary?.eval_utilization_pct || 0) >= 80 ? "#fee2e2" : "#ecfdf5",
                  color: getUtilizationColor(summary?.eval_utilization_pct || 0)
                }}
              >
                {summary?.eval_utilization_pct || 0}%
              </span>
            </div>
          </div>
        </div>

        {/* Card 4: Trạng thái Cảnh báo Ngân Sách */}
        <div className="agentops-kpi-card">
          <div
            className={`kpi-icon-badge ${
              alerts.some(a => a.severity === "CRITICAL") ? "red" : alerts.length > 0 ? "amber" : "emerald"
            }`}
          >
            {alerts.length > 0 ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Trạng Thái Vận Hành</span>
            <div className="kpi-main-val" style={{ fontSize: "17px" }}>
              {alerts.length > 0
                ? `${alerts.length} Sự Kiện Cảnh Báo`
                : "Hệ Thống Bình Thường"}
            </div>
            <span className="kpi-sub-val" style={{ color: alerts.length > 0 ? "#b45309" : "#15803d" }}>
              {alerts.length > 0 ? "Cần kiểm tra ngưỡng ngân sách" : "Tất cả chi phí trong ngưỡng an toàn"}
            </span>
          </div>
        </div>
      </div>

      {/* Tiến độ ngân sách ngày & Thông báo cảnh báo trực quan */}
      <div className="agentops-budget-banner-grid">
        {/* Thanh ngân sách Chat */}
        <div className="budget-progress-card">
          <div className="budget-card-header">
            <div className="budget-card-title">
              <MessageSquare size={16} color="#2563eb" />
              <span>Tiến Độ Ngân Sách Chat Hôm Nay</span>
            </div>
            <span
              className="budget-status-pill"
              style={{
                color: getUtilizationColor(summary?.chat_utilization_pct || 0),
                backgroundColor: (summary?.chat_utilization_pct || 0) >= 100 ? "#fee2e2" : "#f1f5f9"
              }}
            >
              {(summary?.chat_utilization_pct || 0) >= 100
                ? "⛔ Đã chạm trần"
                : (summary?.chat_utilization_pct || 0) >= 80
                ? "⚠️ Ngưỡng cảnh báo"
                : "✅ An toàn"}
            </span>
          </div>

          <div className="budget-bar-track">
            <div
              className="budget-bar-fill"
              style={{
                width: `${Math.min(summary?.chat_utilization_pct || 0, 100)}%`,
                backgroundColor: getUtilizationColor(summary?.chat_utilization_pct || 0)
              }}
            />
          </div>

          <div className="budget-bar-footer">
            <span>Đã dùng: <b>{formatVNDDecimal(summary?.chat_spend_vnd)}</b></span>
            <span>Hạn mức: <b>{formatVND(summary?.chat_daily_limit_vnd)}</b> ({summary?.chat_utilization_pct || 0}%)</span>
          </div>
        </div>

        {/* Thanh ngân sách Evaluation */}
        <div className="budget-progress-card">
          <div className="budget-card-header">
            <div className="budget-card-title">
              <TrendingUp size={16} color="#7c3aed" />
              <span>Tiến Độ Ngân Sách Đánh Giá (Eval/RAG)</span>
            </div>
            <span
              className="budget-status-pill"
              style={{
                color: getUtilizationColor(summary?.eval_utilization_pct || 0),
                backgroundColor: (summary?.eval_utilization_pct || 0) >= 100 ? "#fee2e2" : "#f1f5f9"
              }}
            >
              {(summary?.eval_utilization_pct || 0) >= 100
                ? "⛔ Đã chạm trần"
                : (summary?.eval_utilization_pct || 0) >= 80
                ? "⚠️ Ngưỡng cảnh báo"
                : "✅ An toàn"}
            </span>
          </div>

          <div className="budget-bar-track">
            <div
              className="budget-bar-fill"
              style={{
                width: `${Math.min(summary?.eval_utilization_pct || 0, 100)}%`,
                backgroundColor: getUtilizationColor(summary?.eval_utilization_pct || 0)
              }}
            />
          </div>

          <div className="budget-bar-footer">
            <span>Đã dùng: <b>{formatVNDDecimal(summary?.eval_spend_vnd)}</b></span>
            <span>Hạn mức: <b>{formatVND(summary?.eval_daily_limit_vnd)}</b> ({summary?.eval_utilization_pct || 0}%)</span>
          </div>
        </div>
      </div>

      {/* Cảnh báo chủ động nếu có */}
      {alerts.length > 0 && (
        <div className="agentops-alerts-box">
          <div className="alerts-box-header">
            <ShieldAlert size={18} color="#b91c1c" />
            <h4>Cảnh Báo Vận Hành Đang Kích Hoạt</h4>
          </div>
          <div className="alerts-box-list">
            {alerts.slice(0, 3).map((a, i) => (
              <div key={i} className={`alert-item-row ${a.severity?.toLowerCase()}`}>
                <span className={`badge-severity ${a.severity?.toLowerCase()}`}>
                  {a.severity}
                </span>
                <span className="alert-item-msg">{a.message}</span>
                <span className="alert-item-time">{formatDate(a.created_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Analytics Container with Sub-views */}
      <div className="agentops-table-section">
        {/* Navigation Tabs */}
        <div className="agentops-nav-tabs">
          <button
            className={`agentops-tab-btn ${subView === "models" ? "active" : ""}`}
            onClick={() => setSubView("models")}
          >
            <Cpu size={15} />
            <span>Phân Bổ Theo Mô Hình ({models.length})</span>
          </button>

          <button
            className={`agentops-tab-btn ${subView === "workloads" ? "active" : ""}`}
            onClick={() => setSubView("workloads")}
          >
            <Layers size={15} />
            <span>Theo Loại Tác Vụ ({workloads.length})</span>
          </button>

          <button
            className={`agentops-tab-btn ${subView === "threads" ? "active" : ""}`}
            onClick={() => setSubView("threads")}
          >
            <MessageSquare size={15} />
            <span>Theo Phiên Hội Thoại ({threads.length})</span>
          </button>

          <button
            className={`agentops-tab-btn ${subView === "recent" ? "active" : ""}`}
            onClick={() => setSubView("recent")}
          >
            <Clock size={15} />
            <span>Nhật Ký Gọi Gần Đây ({recentEvents.length})</span>
          </button>

          <button
            className={`agentops-tab-btn ${subView === "budgets" ? "active" : ""}`}
            onClick={() => setSubView("budgets")}
          >
            <Settings size={15} />
            <span>Cấu Hình Hạn Mức ({budgets.length})</span>
          </button>

          {alerts.length > 0 && (
            <button
              className={`agentops-tab-btn ${subView === "alerts" ? "active" : ""}`}
              onClick={() => setSubView("alerts")}
            >
              <AlertTriangle size={15} color="#d97706" />
              <span>Lịch Sử Cảnh Báo ({alerts.length})</span>
            </button>
          )}
        </div>

        {/* Tab 1: Phân bổ theo Model */}
        {subView === "models" && (
          <div className="agentops-table-wrapper">
            <table className="agentops-data-table">
              <thead>
                <tr>
                  <th>Nhà Cung Cấp</th>
                  <th>Tên Mô Hình AI</th>
                  <th style={{ textAlign: "right" }}>Số Cuộc Gọi</th>
                  <th style={{ textAlign: "right" }}>Input Tokens</th>
                  <th style={{ textAlign: "right" }}>Output Tokens</th>
                  <th style={{ textAlign: "right" }}>Tổng Chi Phí (VND)</th>
                  <th style={{ textAlign: "right" }}>Chi Phí (USD)</th>
                  <th style={{ textAlign: "right" }}>Độ Trễ TB</th>
                </tr>
              </thead>
              <tbody>
                {models.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="empty-table-row">
                      Chưa ghi nhận dữ liệu mô hình AI nào.
                    </td>
                  </tr>
                ) : (
                  models.map((m, idx) => (
                    <tr key={idx}>
                      <td>
                        <span className="badge-provider">{m.provider}</span>
                      </td>
                      <td style={{ fontWeight: "600", color: "#0f172a" }}>
                        {m.model_name}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "600" }}>
                        {formatNum(m.total_calls)}
                      </td>
                      <td style={{ textAlign: "right", color: "#475569" }}>
                        {formatNum(m.total_input_tokens)}
                      </td>
                      <td style={{ textAlign: "right", color: "#475569" }}>
                        {formatNum(m.total_output_tokens)}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "700", color: "#1d4ed8" }}>
                        {formatVNDDecimal(m.total_cost_vnd)}
                      </td>
                      <td style={{ textAlign: "right", color: "#64748b", fontSize: "12px" }}>
                        {formatUSD(m.total_cost_usd)}
                      </td>
                      <td style={{ textAlign: "right", color: "#475569" }}>
                        {m.avg_latency_ms ? `${Math.round(m.avg_latency_ms)} ms` : "-"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 2: Phân loại theo Tác Vụ (Workload) */}
        {subView === "workloads" && (
          <div className="agentops-table-wrapper">
            <table className="agentops-data-table">
              <thead>
                <tr>
                  <th>Loại Tác Vụ (Workload)</th>
                  <th style={{ textAlign: "right" }}>Tổng Requests</th>
                  <th style={{ textAlign: "right" }}>Lượt Gọi LLM</th>
                  <th style={{ textAlign: "right" }}>Tổng Input Tokens</th>
                  <th style={{ textAlign: "right" }}>Tổng Output Tokens</th>
                  <th style={{ textAlign: "right" }}>Tổng Chi Phí (VND)</th>
                  <th style={{ textAlign: "right" }}>Chi Phí (USD)</th>
                  <th style={{ textAlign: "right" }}>Chi Phí TB / Lượt</th>
                </tr>
              </thead>
              <tbody>
                {workloads.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="empty-table-row">
                      Chưa có dữ liệu tác vụ nào.
                    </td>
                  </tr>
                ) : (
                  workloads.map((w, idx) => (
                    <tr key={idx}>
                      <td>
                        <span className="badge-workload">{w.workload_type}</span>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "600" }}>
                        {formatNum(w.total_requests)}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {formatNum(w.total_model_calls)}
                      </td>
                      <td style={{ textAlign: "right", color: "#475569" }}>
                        {formatNum(w.total_input_tokens)}
                      </td>
                      <td style={{ textAlign: "right", color: "#475569" }}>
                        {formatNum(w.total_output_tokens)}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "700", color: "#1d4ed8" }}>
                        {formatVNDDecimal(w.total_cost_vnd)}
                      </td>
                      <td style={{ textAlign: "right", color: "#64748b", fontSize: "12px" }}>
                        {formatUSD(w.total_cost_usd)}
                      </td>
                      <td style={{ textAlign: "right", color: "#059669", fontWeight: "600" }}>
                        {formatVNDDecimal(w.avg_cost_per_call_vnd)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 3: Theo Phiên Hội Thoại (Threads) */}
        {subView === "threads" && (
          <div className="agentops-table-wrapper">
            <table className="agentops-data-table">
              <thead>
                <tr>
                  <th>Mã Phiên (Thread ID)</th>
                  <th style={{ textAlign: "right" }}>Số Lượt Hỏi (Turns)</th>
                  <th style={{ textAlign: "right" }}>Lượt Gọi AI</th>
                  <th style={{ textAlign: "right" }}>Tổng Tokens</th>
                  <th style={{ textAlign: "right" }}>Tổng Chi Phí (VND)</th>
                  <th style={{ textAlign: "right" }}>Chi Phí (USD)</th>
                  <th>Hoạt Động Gần Nhất</th>
                </tr>
              </thead>
              <tbody>
                {threads.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="empty-table-row">
                      Chưa ghi nhận phiên hội thoại nào.
                    </td>
                  </tr>
                ) : (
                  threads.map((t, idx) => (
                    <tr key={idx}>
                      <td style={{ fontFamily: "monospace", fontSize: "12px", color: "#1e293b", fontWeight: "600" }}>
                        {t.thread_id}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "600" }}>
                        {formatNum(t.total_turns)}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {formatNum(t.total_calls)}
                      </td>
                      <td style={{ textAlign: "right", color: "#475569" }}>
                        {formatNum(t.total_tokens)}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "700", color: "#1d4ed8" }}>
                        {formatVNDDecimal(t.total_cost_vnd)}
                      </td>
                      <td style={{ textAlign: "right", color: "#64748b", fontSize: "12px" }}>
                        {formatUSD(t.total_cost_usd)}
                      </td>
                      <td style={{ fontSize: "12px", color: "#64748b" }}>
                        {formatDate(t.last_seen)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 4: Nhật Ký Gọi Gần Đây (Recent Events) */}
        {subView === "recent" && (
          <div className="agentops-table-wrapper">
            <table className="agentops-data-table">
              <thead>
                <tr>
                  <th>Thời Gian</th>
                  <th>Mô Hình</th>
                  <th>Tác Vụ</th>
                  <th style={{ textAlign: "right" }}>Input</th>
                  <th style={{ textAlign: "right" }}>Output</th>
                  <th style={{ textAlign: "right" }}>Tổng Tokens</th>
                  <th style={{ textAlign: "right" }}>Độ Trễ</th>
                  <th style={{ textAlign: "right" }}>Chi Phí (VND)</th>
                  <th>Trạng Thái</th>
                </tr>
              </thead>
              <tbody>
                {recentEvents.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="empty-table-row">
                      Chưa có sự kiện gọi LLM nào gần đây.
                    </td>
                  </tr>
                ) : (
                  recentEvents.map((e, idx) => (
                    <tr key={idx}>
                      <td style={{ fontSize: "12px", color: "#64748b", whiteSpace: "nowrap" }}>
                        {formatDate(e.created_at)}
                      </td>
                      <td style={{ fontWeight: "600", color: "#0f172a" }}>
                        {e.model_name}
                      </td>
                      <td>
                        <span className="badge-workload">{e.workload_type}</span>
                      </td>
                      <td style={{ textAlign: "right", color: "#64748b", fontSize: "12px" }}>
                        {formatNum(e.input_tokens)}
                      </td>
                      <td style={{ textAlign: "right", color: "#64748b", fontSize: "12px" }}>
                        {formatNum(e.output_tokens)}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "600" }}>
                        {formatNum(e.total_tokens)}
                      </td>
                      <td style={{ textAlign: "right", color: "#475569" }}>
                        {e.latency_ms ? `${e.latency_ms} ms` : "-"}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "700", color: "#1d4ed8" }}>
                        {formatVNDDecimal(e.cost_vnd)}
                      </td>
                      <td>
                        <span className={`badge-status ${e.execution_status === "SUCCESS" ? "badge-indexed" : "badge-pending"}`}>
                          {e.execution_status || "SUCCESS"}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 5: Cấu Hình Hạn Mức Ngân Sách */}
        {subView === "budgets" && (
          <div className="agentops-table-wrapper">
            <div className="budget-settings-header">
              <div>
                <h4 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a" }}>
                  Bảng Cấu Hình Hạn Mức Chi Tiêu Cho Từng Phân Hệ
                </h4>
                <p style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>
                  Mọi yêu cầu gọi LLM vượt quá hạn mức nguyên tử sẽ bị Budget Guard từ chối (Atomic Budget Rejection).
                </p>
              </div>
              <button
                className="btn-agentops-primary"
                onClick={() => handleOpenBudgetModal(null)}
              >
                + Thêm / Cập Nhật Hạn Mức
              </button>
            </div>

            <table className="agentops-data-table">
              <thead>
                <tr>
                  <th>Loại Tác Vụ</th>
                  <th style={{ textAlign: "right" }}>Hạn Mức Mỗi Lượt (Turn Limit)</th>
                  <th style={{ textAlign: "right" }}>Hạn Mức Mỗi Phiên (Thread Limit)</th>
                  <th style={{ textAlign: "right" }}>Hạn Mức Mỗi Ngày (Daily Limit)</th>
                  <th>Cập Nhật Lần Cuối</th>
                  <th style={{ textAlign: "right" }}>Thao Tác</th>
                </tr>
              </thead>
              <tbody>
                {budgets.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="empty-table-row">
                      Chưa nạp cấu hình hạn mức nào.
                    </td>
                  </tr>
                ) : (
                  budgets.map((b, idx) => (
                    <tr key={idx}>
                      <td>
                        <span className="badge-workload" style={{ fontSize: "13px" }}>
                          {b.workload_type}
                        </span>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "600", color: "#0f172a" }}>
                        {formatVND(b.turn_limit_vnd)}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "600", color: "#0f172a" }}>
                        {formatVND(b.thread_limit_vnd)}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "700", color: "#1d4ed8" }}>
                        {formatVND(b.daily_limit_vnd)}
                      </td>
                      <td style={{ fontSize: "12px", color: "#64748b" }}>
                        {formatDate(b.updated_at)}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          className="btn-action"
                          style={{ background: "#eff6ff", color: "#2563eb" }}
                          onClick={() => handleOpenBudgetModal(b)}
                          title="Chỉnh sửa hạn mức"
                        >
                          <Settings size={13} style={{ marginRight: "4px" }} /> Chỉnh sửa
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 6: Lịch Sử Cảnh Báo (Alerts) */}
        {subView === "alerts" && (
          <div className="agentops-table-wrapper">
            <table className="agentops-data-table">
              <thead>
                <tr>
                  <th>Thời Gian</th>
                  <th>Mức Độ</th>
                  <th>Loại Cảnh Báo</th>
                  <th>Tác Vụ</th>
                  <th style={{ textAlign: "right" }}>Giá Trị Đo</th>
                  <th style={{ textAlign: "right" }}>Ngưỡng</th>
                  <th>Thông Điệp Chi Tiết</th>
                </tr>
              </thead>
              <tbody>
                {alerts.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="empty-table-row">
                      Không có sự kiện cảnh báo nào được ghi nhận.
                    </td>
                  </tr>
                ) : (
                  alerts.map((a, idx) => (
                    <tr key={idx}>
                      <td style={{ fontSize: "12px", color: "#64748b", whiteSpace: "nowrap" }}>
                        {formatDate(a.created_at)}
                      </td>
                      <td>
                        <span className={`badge-severity ${a.severity?.toLowerCase()}`}>
                          {a.severity}
                        </span>
                      </td>
                      <td style={{ fontWeight: "600", fontSize: "12px" }}>
                        {a.alert_type}
                      </td>
                      <td>
                        <span className="badge-workload">{a.workload_type || "toàn hệ thống"}</span>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: "600", color: "#b91c1c" }}>
                        {a.actual_value != null ? formatVNDDecimal(a.actual_value) : "-"}
                      </td>
                      <td style={{ textAlign: "right", color: "#475569" }}>
                        {a.threshold_value != null ? formatVND(a.threshold_value) : "-"}
                      </td>
                      <td style={{ fontSize: "13px", color: "#0f172a" }}>
                        {a.message}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal Cấu Hình Hạn Mức Ngân Sách */}
      {showBudgetModal && (
        <div className="modal-overlay" onClick={() => setShowBudgetModal(false)}>
          <div className="budget-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#0f172a" }}>
                  Thiết Lập Hạn Mức Ngân Sách (AgentOps)
                </h3>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  Đơn vị tính: Việt Nam Đồng (VND). Ngân sách được bảo vệ nguyên tử qua PostgreSQL.
                </span>
              </div>
              <button
                onClick={() => setShowBudgetModal(false)}
                style={{ border: "none", background: "transparent", cursor: "pointer" }}
              >
                <X size={20} color="#64748b" />
              </button>
            </div>

            {modalFeedback && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: "8px",
                  marginBottom: "16px",
                  fontSize: "13px",
                  background: modalFeedback.type === "success" ? "#ecfdf5" : "#fef2f2",
                  color: modalFeedback.type === "success" ? "#065f46" : "#991b1b",
                  border: `1px solid ${modalFeedback.type === "success" ? "#a7f3d0" : "#fecaca"}`
                }}
              >
                {modalFeedback.message}
              </div>
            )}

            <form onSubmit={handleSaveBudget}>
              <div className="form-group">
                <label>Loại Tác Vụ (Workload Type)</label>
                <select
                  value={editingBudget.workload_type}
                  onChange={(e) => setEditingBudget({ ...editingBudget, workload_type: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "13px",
                    outline: "none"
                  }}
                >
                  <option value="chat">chat (Khung chat tư vấn BĐS)</option>
                  <option value="evaluation">evaluation (Đánh giá Ragas/DeepEval)</option>
                  <option value="default">default (Mặc định)</option>
                </select>
              </div>

              <div className="form-group">
                <label>Hạn Mức Mỗi Lượt Gọi (Turn Limit - VND)</label>
                <input
                  type="number"
                  min="500"
                  step="500"
                  required
                  value={editingBudget.turn_limit_vnd}
                  onChange={(e) => setEditingBudget({ ...editingBudget, turn_limit_vnd: e.target.value })}
                  placeholder="5000"
                />
                <span className="field-hint">Ngưỡng tối đa cho 1 lượt phản hồi của AI (mặc định: 5.000 ₫)</span>
              </div>

              <div className="form-group">
                <label>Hạn Mức Mỗi Phiên (Thread Limit - VND)</label>
                <input
                  type="number"
                  min="2000"
                  step="1000"
                  required
                  value={editingBudget.thread_limit_vnd}
                  onChange={(e) => setEditingBudget({ ...editingBudget, thread_limit_vnd: e.target.value })}
                  placeholder="20000"
                />
                <span className="field-hint">Ngưỡng tối đa cho một phiên hội thoại của người dùng (mặc định: 20.000 ₫)</span>
              </div>

              <div className="form-group">
                <label>Hạn Mức Ngày (Daily Limit - VND)</label>
                <input
                  type="number"
                  min="10000"
                  step="10000"
                  required
                  value={editingBudget.daily_limit_vnd}
                  onChange={(e) => setEditingBudget({ ...editingBudget, daily_limit_vnd: e.target.value })}
                  placeholder="200000"
                />
                <span className="field-hint">Ngân sách trần trong 1 ngày cho tác vụ này (mặc định: 200.000 ₫)</span>
              </div>

              <div style={{ marginTop: "20px", display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowBudgetModal(false)}
                  style={{
                    padding: "8px 16px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    background: "#fff",
                    cursor: "pointer",
                    fontSize: "13px"
                  }}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className="btn-book"
                  disabled={savingBudget}
                  style={{ padding: "8px 20px" }}
                >
                  {savingBudget ? "Đang lưu..." : "Lưu Hạn Mức"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
