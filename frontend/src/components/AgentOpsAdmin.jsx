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
  ChevronRight,
  Users,
  Plus,
  Trash2,
  Edit3,
  UserCheck,
  Shield
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
  const [userWallets, setUserWallets] = useState([]);
  const [userGroups, setUserGroups] = useState([]);

  // Sub-view tab trong AgentOps: "models" | "workloads" | "threads" | "recent" | "alerts" | "budgets" | "user_limits"
  const [subView, setSubView] = useState("models");

  // State Modal Cấu hình Ngân Sách Hệ Thống
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [editingBudget, setEditingBudget] = useState({
    workload_type: "chat",
    turn_limit_vnd: 5000,
    thread_limit_vnd: 20000,
    daily_limit_vnd: 200000
  });
  const [savingBudget, setSavingBudget] = useState(false);
  const [modalFeedback, setModalFeedback] = useState(null);

  // State Modal Cấu hình Nhóm Người Dùng (Thêm / Sửa nhóm)
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [isEditingExistingGroup, setIsEditingExistingGroup] = useState(false);
  const [editingGroup, setEditingGroup] = useState({
    group_code: "",
    group_name: "",
    daily_free_limit_vnd: 5000,
    description: "",
    is_default: false
  });
  const [savingGroup, setSavingGroup] = useState(false);
  const [groupFeedback, setGroupFeedback] = useState(null);

  // State Modal Gán Nhóm cho User (Đổi nhóm người dùng)
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [editingAssign, setEditingAssign] = useState({
    user_id: "",
    current_group: "standard",
    new_group_code: "standard"
  });
  const [savingAssign, setSavingAssign] = useState(false);
  const [assignFeedback, setAssignFeedback] = useState(null);

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
        budgetsRes,
        userWalletsRes,
        userGroupsRes
      ] = await Promise.all([
        fetch(`${API_BASE}/api/agentops/reports/summary`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/api/agentops/reports/model`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/agentops/reports/workload`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/agentops/reports/thread?limit=25`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/agentops/reports/recent-events?limit=25`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/agentops/alerts/history?limit=25`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/agentops/budgets`).then(r => r.json()).catch(() => ({ budgets: [] })),
        fetch(`${API_BASE}/api/admin/user-wallets`).then(r => r.json()).catch(() => ({ users: [] })),
        fetch(`${API_BASE}/api/user/groups`).then(r => r.json()).catch(() => ({ groups: [] }))
      ]);

      if (summaryRes) setSummary(summaryRes);
      if (Array.isArray(modelsRes)) setModels(modelsRes);
      if (Array.isArray(workloadsRes)) setWorkloads(workloadsRes);
      if (Array.isArray(threadsRes)) setThreads(threadsRes);
      if (Array.isArray(recentRes)) setRecentEvents(recentRes);
      if (Array.isArray(alertsRes)) setAlerts(alertsRes);
      if (budgetsRes && Array.isArray(budgetsRes.budgets)) setBudgets(budgetsRes.budgets);
      if (userWalletsRes && Array.isArray(userWalletsRes.users)) setUserWallets(userWalletsRes.users);
      if (userGroupsRes && Array.isArray(userGroupsRes.groups)) setUserGroups(userGroupsRes.groups);
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

  // ================= QUẢN LÝ NHÓM NGƯỜI DÙNG & HẠN MỨC FREE =================
  const handleOpenGroupModal = (group = null) => {
    if (group) {
      setIsEditingExistingGroup(true);
      setEditingGroup({
        group_code: group.group_code,
        group_name: group.group_name || "",
        daily_free_limit_vnd: group.daily_free_limit_vnd || 5000,
        description: group.description || "",
        is_default: Boolean(group.is_default)
      });
    } else {
      setIsEditingExistingGroup(false);
      setEditingGroup({
        group_code: "",
        group_name: "",
        daily_free_limit_vnd: 5000,
        description: "",
        is_default: false
      });
    }
    setGroupFeedback(null);
    setShowGroupModal(true);
  };

  const handleSaveGroup = async (e) => {
    e.preventDefault();
    setSavingGroup(true);
    setGroupFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/user/groups`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          group_code: editingGroup.group_code.trim().toLowerCase(),
          group_name: editingGroup.group_name.trim(),
          daily_free_limit_vnd: Number(editingGroup.daily_free_limit_vnd),
          description: editingGroup.description.trim(),
          is_default: Boolean(editingGroup.is_default)
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || "Không thể lưu cấu hình nhóm");
      }
      setGroupFeedback({
        type: "success",
        message: `Đã lưu nhóm "${editingGroup.group_name}" với hạn mức ${formatVND(editingGroup.daily_free_limit_vnd)}/ngày thành công!`
      });
      setTimeout(() => {
        setShowGroupModal(false);
        loadAgentOpsData(true);
      }, 1000);
    } catch (err) {
      setGroupFeedback({ type: "error", message: `Lỗi: ${err.message}` });
    } finally {
      setSavingGroup(false);
    }
  };

  const handleDeleteGroup = async (groupCode, groupName) => {
    if (groupCode === "standard") {
      alert("Không thể xóa nhóm mặc định 'standard'. Nhóm này dùng làm nhóm cơ sở cho toàn bộ hệ thống.");
      return;
    }
    if (!window.confirm(`Bạn có chắc muốn xóa nhóm "${groupName}" (${groupCode})? Các thành viên thuộc nhóm này sẽ tự động chuyển về nhóm mặc định (standard).`)) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/user/groups/${encodeURIComponent(groupCode)}`, {
        method: "DELETE"
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || "Xóa nhóm thất bại");
      }
      loadAgentOpsData(true);
    } catch (err) {
      alert("Lỗi xóa nhóm: " + err.message);
    }
  };

  // ================= GÁN NHÓM CHO NGƯỜI DÙNG =================
  const handleOpenAssignModal = (userWallet) => {
    setEditingAssign({
      user_id: userWallet.user_id,
      current_group: userWallet.user_group || "standard",
      new_group_code: userWallet.user_group || "standard"
    });
    setAssignFeedback(null);
    setShowAssignModal(true);
  };

  const handleSaveAssign = async (e) => {
    e.preventDefault();
    setSavingAssign(true);
    setAssignFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/user/wallet/set-group`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: editingAssign.user_id,
          group_code: editingAssign.new_group_code
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || "Không thể chuyển nhóm người dùng");
      }
      setAssignFeedback({
        type: "success",
        message: `Đã chuyển người dùng "${editingAssign.user_id}" sang nhóm mới thành công!`
      });
      setTimeout(() => {
        setShowAssignModal(false);
        loadAgentOpsData(true);
      }, 1000);
    } catch (err) {
      setAssignFeedback({ type: "error", message: `Lỗi: ${err.message}` });
    } finally {
      setSavingAssign(false);
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

          <button
            className={`agentops-tab-btn ${subView === "user_limits" ? "active" : ""}`}
            onClick={() => setSubView("user_limits")}
          >
            <Users size={15} />
            <span>Nhóm & Hạn Mức Free ({userGroups.length})</span>
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

        {/* Tab: Quản Lý Nhóm & Hạn Mức Miễn Phí User */}
        {subView === "user_limits" && (
          <div className="agentops-table-wrapper">
            {/* PHẦN 1: BẢNG CẤU HÌNH CÁC NHÓM NGƯỜI DÙNG */}
            <div className="budget-settings-header" style={{ marginBottom: "16px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
              <div>
                <h3 className="budget-settings-title" style={{ display: "flex", alignItems: "center", gap: "8px", margin: "0 0 6px 0" }}>
                  <Shield size={18} color="#2563eb" />
                  Cấu Hình Hạn Mức Miễn Phí Theo Nhóm Người Dùng (User Groups)
                </h3>
                <p className="budget-settings-desc" style={{ margin: 0, color: "#64748b", fontSize: "13px" }}>
                  Chỉ cần thiết lập hạn mức hàng ngày theo nhóm (ví dụ: standard 5.000đ, VIP 10.000đ, PRO 20.000đ,...). Các nhóm mới được thêm và điều chỉnh linh động, toàn bộ người dùng thuộc nhóm sẽ tự động được áp dụng.
                </p>
              </div>
              <button
                type="button"
                className="btn-agentops-primary"
                onClick={() => handleOpenGroupModal(null)}
                style={{ display: "flex", alignItems: "center", gap: "6px", padding: "8px 14px", fontSize: "13px" }}
              >
                <Plus size={15} /> Thêm Nhóm Mới
              </button>
            </div>

            <table className="agentops-data-table" style={{ marginBottom: "32px" }}>
              <thead>
                <tr>
                  <th>Mã Nhóm</th>
                  <th>Tên Nhóm</th>
                  <th style={{ textAlign: "right" }}>Hạn Mức Free / Ngày</th>
                  <th style={{ textAlign: "center" }}>Số Người Dùng</th>
                  <th style={{ textAlign: "center" }}>Mặc Định</th>
                  <th>Mô Tả Nhóm</th>
                  <th style={{ textAlign: "center" }}>Thao Tác</th>
                </tr>
              </thead>
              <tbody>
                {userGroups.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="empty-table-row">
                      Đang tải danh sách nhóm người dùng...
                    </td>
                  </tr>
                ) : (
                  userGroups.map((g) => (
                    <tr key={g.group_code}>
                      <td>
                        <span className="badge-user-group-code">
                          <code>{g.group_code}</code>
                        </span>
                      </td>
                      <td style={{ fontWeight: 600, color: "#0f172a" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          {g.group_code === "vip" ? "⭐ " : g.group_code === "pro" ? "🚀 " : "👤 "}
                          <span>{g.group_name}</span>
                        </div>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 700, color: "#0284c7", fontSize: "14px" }}>
                        {formatVND(g.daily_free_limit_vnd)}
                      </td>
                      <td style={{ textAlign: "center", fontWeight: 600, color: "#475569" }}>
                        <span className="agentops-pill" style={{ background: "#f1f5f9", padding: "3px 10px", borderRadius: "12px", fontSize: "12px" }}>
                          {g.total_users || 0} user
                        </span>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        {g.is_default ? (
                          <span className="badge-default-group">Mặc định</span>
                        ) : (
                          <span style={{ color: "#94a3b8" }}>-</span>
                        )}
                      </td>
                      <td style={{ fontSize: "12px", color: "#64748b", maxWidth: "260px" }}>
                        {g.description || "-"}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <div style={{ display: "flex", gap: "6px", justifyContent: "center" }}>
                          <button
                            className="btn-action"
                            style={{ background: "#eff6ff", color: "#2563eb", border: "1px solid #bfdbfe", padding: "4px 8px", borderRadius: "6px", fontSize: "12px" }}
                            onClick={() => handleOpenGroupModal(g)}
                            title="Chỉnh sửa hạn mức & tên nhóm"
                          >
                            <Edit3 size={13} style={{ marginRight: "3px" }} /> Sửa
                          </button>
                          {g.group_code !== "standard" && (
                            <button
                              className="btn-action"
                              style={{ background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca", padding: "4px 8px", borderRadius: "6px", fontSize: "12px" }}
                              onClick={() => handleDeleteGroup(g.group_code, g.group_name)}
                              title="Xóa nhóm này"
                            >
                              <Trash2 size={13} style={{ marginRight: "3px" }} /> Xóa
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            {/* PHẦN 2: BẢNG DANH SÁCH NGƯỜI DÙNG & GÁN NHÓM */}
            <div className="budget-settings-header" style={{ marginBottom: "16px" }}>
              <div>
                <h3 className="budget-settings-title" style={{ display: "flex", alignItems: "center", gap: "8px", margin: "0 0 6px 0" }}>
                  <Users size={18} color="#0284c7" />
                  Danh Sách Người Dùng & Phân Nhóm Hiện Tại ({userWallets.length} người dùng)
                </h3>
                <p className="budget-settings-desc" style={{ margin: 0, color: "#64748b", fontSize: "13px" }}>
                  Từng người dùng sẽ tự động nhận hạn mức free mỗi ngày theo nhóm được gán. Bấm "Đổi Nhóm" để phân lại nhóm (ví dụ nâng cấp VIP cho user).
                </p>
              </div>
            </div>

            <table className="agentops-data-table">
              <thead>
                <tr>
                  <th>Mã Người Dùng (User ID)</th>
                  <th>Nhóm Thành Viên</th>
                  <th style={{ textAlign: "right" }}>Hạn Mức Theo Nhóm</th>
                  <th style={{ textAlign: "right" }}>Đã Dùng Hôm Nay</th>
                  <th style={{ textAlign: "right" }}>Còn Lại Hôm Nay</th>
                  <th style={{ textAlign: "right" }}>Số Dư Ví Nạp</th>
                  <th style={{ textAlign: "center" }}>Trạng Thái</th>
                  <th style={{ textAlign: "center" }}>Thao Tác</th>
                </tr>
              </thead>
              <tbody>
                {userWallets.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="empty-table-row">
                      Chưa có dữ liệu người dùng nào trong hệ thống.
                    </td>
                  </tr>
                ) : (
                  userWallets.map((u) => (
                    <tr key={u.user_id}>
                      <td style={{ fontWeight: 600, color: "#1e293b" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ display: "inline-block", width: "8px", height: "8px", borderRadius: "50%", background: u.can_chat ? "#10b981" : "#ef4444" }}></span>
                          <code>{u.user_id}</code>
                        </div>
                      </td>
                      <td>
                        <span className={`badge-user-tier ${u.user_group || "standard"}`}>
                          {u.group_name || u.user_group || "Người dùng thường"}
                        </span>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 700, color: "#0284c7" }}>
                        {formatVND(u.daily_free_limit_vnd)}
                      </td>
                      <td style={{ textAlign: "right", color: u.daily_free_spent_vnd > 0 ? "#d97706" : "#64748b" }}>
                        {formatVND(u.daily_free_spent_vnd)}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 600, color: u.daily_free_remaining_vnd > 0 ? "#10b981" : "#ef4444" }}>
                        {formatVND(u.daily_free_remaining_vnd)}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 600 }}>
                        {formatVND(u.balance_vnd)}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        {u.can_chat ? (
                          <span className="agentops-pill" style={{ background: "#ecfdf5", color: "#059669", border: "1px solid #a7f3d0", padding: "3px 8px", borderRadius: "12px", fontSize: "11px", fontWeight: 600 }}>
                            Sẵn sàng
                          </span>
                        ) : (
                          <span className="agentops-pill" style={{ background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca", padding: "3px 8px", borderRadius: "12px", fontSize: "11px", fontWeight: 600 }}>
                            Hết hạn mức
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <button
                          className="btn-action"
                          style={{ background: "#f0f9ff", color: "#0284c7", border: "1px solid #bae6fd", cursor: "pointer", padding: "5px 10px", borderRadius: "6px", fontSize: "12px", fontWeight: 600 }}
                          onClick={() => handleOpenAssignModal(u)}
                          title="Đổi nhóm phân quyền cho người dùng này"
                        >
                          <UserCheck size={13} style={{ marginRight: "4px" }} /> Đổi Nhóm
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

      {/* Modal 1: Thêm / Sửa Nhóm Người Dùng & Hạn Mức */}
      {showGroupModal && (
        <div className="modal-overlay" onClick={() => setShowGroupModal(false)}>
          <div className="budget-modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "500px" }}>
            <div className="modal-header">
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#0f172a", display: "flex", alignItems: "center", gap: "8px" }}>
                  <Shield size={18} color="#2563eb" />
                  {isEditingExistingGroup ? `Chỉnh Sửa Nhóm "${editingGroup.group_name}"` : "Thêm Nhóm Người Dùng Mới"}
                </h3>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  Hạn mức free hàng ngày sẽ áp dụng tự động cho toàn bộ user trong nhóm này.
                </span>
              </div>
              <button
                onClick={() => setShowGroupModal(false)}
                style={{ border: "none", background: "transparent", cursor: "pointer" }}
              >
                <X size={18} />
              </button>
            </div>

            {groupFeedback && (
              <div
                className={`budget-modal-feedback ${groupFeedback.type}`}
                style={{
                  padding: "10px 14px",
                  borderRadius: "8px",
                  margin: "12px 0",
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  background: groupFeedback.type === "success" ? "#ecfdf5" : "#fef2f2",
                  color: groupFeedback.type === "success" ? "#065f46" : "#991b1b",
                  border: `1px solid ${groupFeedback.type === "success" ? "#a7f3d0" : "#fecaca"}`
                }}
              >
                {groupFeedback.type === "success" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                <span>{groupFeedback.message}</span>
              </div>
            )}

            <form onSubmit={handleSaveGroup}>
              <div className="form-group" style={{ marginBottom: "14px" }}>
                <label style={{ display: "block", marginBottom: "6px", fontWeight: 600, fontSize: "13px" }}>
                  Mã Nhóm (Group Code)
                </label>
                <input
                  type="text"
                  required
                  disabled={isEditingExistingGroup}
                  value={editingGroup.group_code}
                  onChange={(e) => setEditingGroup({ ...editingGroup, group_code: e.target.value })}
                  placeholder="ví dụ: vip, premium, partner..."
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    background: isEditingExistingGroup ? "#f8fafc" : "#ffffff",
                    color: isEditingExistingGroup ? "#64748b" : "#0f172a",
                    fontSize: "13px",
                    boxSizing: "border-box"
                  }}
                />
                <span style={{ fontSize: "11px", color: "#94a3b8", marginTop: "3px", display: "block" }}>
                  Mã định danh viết liền, không dấu (ví dụ: standard, vip, pro, enterprise)
                </span>
              </div>

              <div className="form-group" style={{ marginBottom: "14px" }}>
                <label style={{ display: "block", marginBottom: "6px", fontWeight: 600, fontSize: "13px" }}>
                  Tên Hiển Thị Nhóm (Group Name)
                </label>
                <input
                  type="text"
                  required
                  value={editingGroup.group_name}
                  onChange={(e) => setEditingGroup({ ...editingGroup, group_name: e.target.value })}
                  placeholder="ví dụ: Khách Hàng VIP, Người Dùng Thường..."
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "13px",
                    boxSizing: "border-box"
                  }}
                />
              </div>

              <div className="form-group" style={{ marginBottom: "14px" }}>
                <label style={{ display: "block", marginBottom: "6px", fontWeight: 600, fontSize: "13px" }}>
                  Hạn Mức Miễn Phí Mỗi Ngày (VND)
                </label>
                <input
                  type="number"
                  min="0"
                  step="1000"
                  required
                  value={editingGroup.daily_free_limit_vnd}
                  onChange={(e) => setEditingGroup({ ...editingGroup, daily_free_limit_vnd: Number(e.target.value) })}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "16px",
                    fontWeight: 700,
                    color: "#0284c7",
                    boxSizing: "border-box"
                  }}
                />
                <span className="field-hint" style={{ display: "block", marginTop: "4px", fontSize: "12px", color: "#64748b" }}>
                  Đang chọn: <b>{formatVND(editingGroup.daily_free_limit_vnd)}</b> / ngày cho mỗi user thuộc nhóm
                </span>
              </div>

              {/* Mức gợi ý nhanh */}
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", marginBottom: "6px", fontSize: "12px", color: "#64748b" }}>
                  Chọn nhanh các mức phổ biến:
                </label>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {[5000, 10000, 20000, 50000, 100000].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setEditingGroup({ ...editingGroup, daily_free_limit_vnd: preset })}
                      style={{
                        padding: "5px 12px",
                        fontSize: "12px",
                        borderRadius: "6px",
                        border: editingGroup.daily_free_limit_vnd === preset ? "1.5px solid #0284c7" : "1px solid #e2e8f0",
                        background: editingGroup.daily_free_limit_vnd === preset ? "#e0f2fe" : "#ffffff",
                        color: editingGroup.daily_free_limit_vnd === preset ? "#0284c7" : "#475569",
                        cursor: "pointer",
                        fontWeight: editingGroup.daily_free_limit_vnd === preset ? 600 : 400
                      }}
                    >
                      {preset === 5000 ? "5k (Standard)" : preset === 10000 ? "10k (VIP)" : `${preset / 1000}k`}
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: "14px" }}>
                <label style={{ display: "block", marginBottom: "6px", fontWeight: 600, fontSize: "13px" }}>
                  Mô Tả Nhóm
                </label>
                <textarea
                  rows={2}
                  value={editingGroup.description}
                  onChange={(e) => setEditingGroup({ ...editingGroup, description: e.target.value })}
                  placeholder="Ghi chú về đối tượng người dùng hoặc quyền lợi của nhóm..."
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "13px",
                    boxSizing: "border-box"
                  }}
                />
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer", color: "#334155" }}>
                  <input
                    type="checkbox"
                    checked={editingGroup.is_default}
                    onChange={(e) => setEditingGroup({ ...editingGroup, is_default: e.target.checked })}
                    style={{ width: "16px", height: "16px", cursor: "pointer" }}
                  />
                  <span>Đặt làm nhóm mặc định cho người dùng mới</span>
                </label>
              </div>

              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowGroupModal(false)}
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
                  disabled={savingGroup}
                  style={{
                    padding: "8px 20px",
                    borderRadius: "6px",
                    border: "none",
                    background: "#2563eb",
                    color: "#fff",
                    fontWeight: 600,
                    cursor: "pointer",
                    fontSize: "13px"
                  }}
                >
                  {savingGroup ? "Đang lưu..." : isEditingExistingGroup ? "Cập Nhật Nhóm" : "Tạo Nhóm Mới"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 2: Gán Nhóm Cho Người Dùng (Assign Group) */}
      {showAssignModal && (
        <div className="modal-overlay" onClick={() => setShowAssignModal(false)}>
          <div className="budget-modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "460px" }}>
            <div className="modal-header">
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#0f172a", display: "flex", alignItems: "center", gap: "8px" }}>
                  <UserCheck size={18} color="#0284c7" />
                  Đổi Nhóm Cho Người Dùng
                </h3>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  Chuyển người dùng sang nhóm mới để cập nhật hạn mức free tự động.
                </span>
              </div>
              <button
                onClick={() => setShowAssignModal(false)}
                style={{ border: "none", background: "transparent", cursor: "pointer" }}
              >
                <X size={18} />
              </button>
            </div>

            {assignFeedback && (
              <div
                className={`budget-modal-feedback ${assignFeedback.type}`}
                style={{
                  padding: "10px 14px",
                  borderRadius: "8px",
                  margin: "12px 0",
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  background: assignFeedback.type === "success" ? "#ecfdf5" : "#fef2f2",
                  color: assignFeedback.type === "success" ? "#065f46" : "#991b1b",
                  border: `1px solid ${assignFeedback.type === "success" ? "#a7f3d0" : "#fecaca"}`
                }}
              >
                {assignFeedback.type === "success" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                <span>{assignFeedback.message}</span>
              </div>
            )}

            <form onSubmit={handleSaveAssign}>
              <div className="form-group" style={{ marginBottom: "14px" }}>
                <label style={{ display: "block", marginBottom: "6px", fontWeight: 600, fontSize: "13px" }}>
                  Mã Người Dùng (User ID)
                </label>
                <input
                  type="text"
                  value={editingAssign.user_id}
                  disabled
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    background: "#f8fafc",
                    color: "#64748b",
                    fontSize: "13px",
                    boxSizing: "border-box"
                  }}
                />
              </div>

              <div className="form-group" style={{ marginBottom: "18px" }}>
                <label style={{ display: "block", marginBottom: "6px", fontWeight: 600, fontSize: "13px" }}>
                  Chọn Nhóm Thành Viên Mới
                </label>
                <select
                  value={editingAssign.new_group_code}
                  onChange={(e) => setEditingAssign({ ...editingAssign, new_group_code: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: "6px",
                    border: "1.5px solid #0284c7",
                    fontSize: "14px",
                    fontWeight: 600,
                    color: "#0f172a",
                    background: "#fff",
                    boxSizing: "border-box"
                  }}
                >
                  {userGroups.map((g) => (
                    <option key={g.group_code} value={g.group_code}>
                      {g.group_name} ({g.group_code}) — {formatVND(g.daily_free_limit_vnd)}/ngày
                    </option>
                  ))}
                </select>
                <span style={{ fontSize: "12px", color: "#64748b", marginTop: "6px", display: "block" }}>
                  Người dùng sẽ nhận ngay hạn mức free của nhóm mới trong các lượt tương tác tiếp theo.
                </span>
              </div>

              <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowAssignModal(false)}
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
                  disabled={savingAssign}
                  style={{
                    padding: "8px 20px",
                    borderRadius: "6px",
                    border: "none",
                    background: "#0284c7",
                    color: "#fff",
                    fontWeight: 600,
                    cursor: "pointer",
                    fontSize: "13px"
                  }}
                >
                  {savingAssign ? "Đang lưu..." : "Xác Nhận Đổi Nhóm"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
