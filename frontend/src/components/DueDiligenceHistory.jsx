// frontend/src/components/DueDiligenceHistory.jsx
import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  History,
  Search,
  Filter,
  RotateCw,
  Settings,
  Calendar,
  MapPin,
  ExternalLink,
  Zap,
  ShieldCheck,
  AlertTriangle,
  AlertCircle,
  FileText,
  User,
  Users,
  Trash2
} from "lucide-react";
import "./DueDiligenceHistory.css";

const getVerdictBadge = (verdict) => {
  switch (verdict) {
    case "STRONGLY_RECOMMENDED":
      return {
        label: "Khuyến nghị mạnh (An toàn)",
        className: "badge-green",
        icon: ShieldCheck
      };
    case "PROCEED_WITH_CAUTION":
      return {
        label: "Cần thận trọng (Đàm phán thêm)",
        className: "badge-amber",
        icon: AlertTriangle
      };
    case "HIGH_RISK_AVOID":
      return {
        label: "Rủi ro cao (Cân nhắc tránh)",
        className: "badge-red",
        icon: AlertCircle
      };
    default:
      return {
        label: (typeof verdict === "string" ? verdict : "Đã thẩm định") || "Đã thẩm định",
        className: "badge-gray",
        icon: FileText
      };
  }
};

const formatPriceVND = (price) => {
  if (!price) return "Thương lượng";
  const num = Number(price);
  if (num >= 1000000000) {
    return (num / 1000000000).toFixed(2).replace(/\.00$/, "") + " tỷ";
  }
  if (num >= 1000000) {
    return (num / 1000000).toFixed(0) + " triệu";
  }
  return num.toLocaleString("vi-VN") + " ₫";
};

const formatDate = (isoStr) => {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    return d.toLocaleString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
    });
  } catch (e) {
    return isoStr;
  }
};

export default function DueDiligenceHistory({
  API_BASE = "",
  userId = "",
  onOpenDossier = null,
  onOpenSettings = null
}) {
  const [historyList, setHistoryList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [scope, setScope] = useState("all"); // "user" | "all"
  const [searchQuery, setSearchQuery] = useState("");
  const [districtFilter, setDistrictFilter] = useState("all");
  const [verdictFilter, setVerdictFilter] = useState("all");
  const [settings, setSettings] = useState(null);
  const [openingTaskId, setOpeningTaskId] = useState(null);
  const [deletingTaskId, setDeletingTaskId] = useState(null);
  const [clearingTest, setClearingTest] = useState(false);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/due-diligence/settings`);
      const data = await res.json();
      if (res.ok && data.success) {
        setSettings(data.settings);
      }
    } catch (e) {
      console.warn("Lỗi tải cài đặt DD:", e);
    }
  }, [API_BASE]);

  const fetchHistory = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const url = `${API_BASE}/api/due-diligence/history?scope=${scope}${userId ? `&user_id=${encodeURIComponent(userId)}` : ""}&limit=100`;
      const res = await fetch(url);
      const data = await res.json();
      if (res.ok && data.success) {
        setHistoryList(data.history || []);
      }
    } catch (e) {
      console.error("Lỗi tải lịch sử thẩm định:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [API_BASE, scope, userId]);

  useEffect(() => {
    fetchHistory();
    fetchSettings();
  }, [fetchHistory, fetchSettings]);

  const handleOpenDetail = async (item) => {
    setOpeningTaskId(item.task_id);
    try {
      const res = await fetch(`${API_BASE}/api/due-diligence/history/${item.task_id}`);
      const data = await res.json();
      if (res.ok && data.success && data.task) {
        const fullTask = data.task;
        const dossierData = fullTask.dossier_data;
        const requestData = fullTask.request_data;
        if (onOpenDossier) {
          onOpenDossier(dossierData, requestData, fullTask.task_id, Boolean(fullTask.is_cached));
        }
      } else {
        alert("Không thể tải chi tiết hồ sơ thẩm định này.");
      }
    } catch (e) {
      alert("Lỗi tải chi tiết hồ sơ: " + e.message);
    } finally {
      setOpeningTaskId(null);
    }
  };

  const handleDeleteHistoryItem = async (e, item) => {
    e.stopPropagation();
    if (!item.task_id) return;
    const title = item.property_title || "BĐS này";
    if (!window.confirm(`Bạn có chắc chắn muốn XÓA VĨNH VIỄN hồ sơ thẩm định "${title}" khỏi lịch sử?`)) {
      return;
    }
    setDeletingTaskId(item.task_id);
    try {
      const res = await fetch(`${API_BASE}/api/due-diligence/history/${item.task_id}`, {
        method: "DELETE"
      });
      const data = await res.json();
      if (res.ok && data.success) {
        // Cập nhật state ngay lập tức để biến mất khỏi màn hình
        setHistoryList((prev) => prev.filter((h) => h.task_id !== item.task_id));
      } else {
        alert("Không thể xóa: " + (data.detail || data.message || "Lỗi không xác định"));
      }
    } catch (err) {
      alert("Lỗi khi xóa hồ sơ thẩm định: " + err.message);
    } finally {
      setDeletingTaskId(null);
    }
  };

  const handleClearTestData = async () => {
    if (!window.confirm("Bạn có chắc chắn muốn dọn dẹp và XÓA TOÀN BỘ dữ liệu thẩm định thử nghiệm (test) khỏi database?")) {
      return;
    }
    setClearingTest(true);
    try {
      const res = await fetch(`${API_BASE}/api/due-diligence/history?scope=test`, {
        method: "DELETE"
      });
      const data = await res.json();
      if (res.ok && data.success) {
        alert(`Đã dọn dẹp thành công ${data.cleared_count} bản ghi thử nghiệm!`);
        fetchHistory(true);
      } else {
        alert("Không thể dọn dẹp dữ liệu test: " + (data.detail || "Lỗi server"));
      }
    } catch (err) {
      alert("Lỗi khi dọn dẹp dữ liệu test: " + err.message);
    } finally {
      setClearingTest(false);
    }
  };

  // Lọc danh sách theo thanh tìm kiếm và bộ lọc
  const filteredList = useMemo(() => {
    if (!Array.isArray(historyList)) return [];
    return historyList.filter((item) => {
      if (!item) return false;
      // 1. Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const titleMatch = (item.property_title || "").toLowerCase().includes(q);
        const districtMatch = (item.district || "").toLowerCase().includes(q);
        const wardMatch = (item.ward || "").toLowerCase().includes(q);
        if (!titleMatch && !districtMatch && !wardMatch) return false;
      }
      // 2. District filter
      if (districtFilter !== "all" && item.district !== districtFilter) {
        return false;
      }
      // 3. Verdict filter
      if (verdictFilter !== "all" && item.verdict !== verdictFilter) {
        return false;
      }
      return true;
    });
  }, [historyList, searchQuery, districtFilter, verdictFilter]);

  // Thống kê nhanh
  const stats = useMemo(() => {
    const list = Array.isArray(historyList) ? historyList : [];
    const total = list.length;
    const cachedCount = list.filter((h) => h?.is_cached).length;
    const cacheTtl = settings?.cache_ttl_hours || 48;
    return {
      total,
      cachedCount,
      cacheTtl,
      cacheEnabled: settings?.cache_enabled !== false
    };
  }, [historyList, settings]);

  const uniqueDistricts = useMemo(() => {
    const set = new Set();
    if (Array.isArray(historyList)) {
      historyList.forEach((h) => {
        if (h?.district) set.add(h.district);
      });
    }
    return Array.from(set);
  }, [historyList]);

  return (
    <div className="dd-history-container">
      {/* Top Banner & Header */}
      <div className="dd-history-header">
        <div className="header-info">
          <div className="title-row">
            <History size={26} className="icon-blue" />
            <h2>Hồ Sơ & Lịch Sử Thẩm Định BĐS Đà Nẵng</h2>
          </div>
          <p className="description">
            Kho lưu trữ toàn bộ các hồ sơ thẩm định chuyên sâu (Pháp lý, Quy hoạch, Ngập lụt, Định giá & Tài chính).
            Tài sản được thẩm định trong vòng <strong>{stats.cacheTtl} giờ</strong> sẽ được tái sử dụng kết quả ngay tức khắc (<span className="text-green">0 ₫ & 100% miễn phí</span>).
          </p>
        </div>

        <div className="header-actions">
          <button
            className="btn-refresh"
            onClick={() => fetchHistory(true)}
            disabled={refreshing || loading}
            title="Làm mới danh sách"
          >
            <RotateCw size={16} className={refreshing ? "spin" : ""} />
            <span>Làm Mới</span>
          </button>
          <button
            className="btn-clear-test"
            onClick={handleClearTestData}
            disabled={clearingTest || loading}
            title="Xóa sạch các bản ghi thử nghiệm (test) khỏi cơ sở dữ liệu"
          >
            <Trash2 size={16} />
            <span>{clearingTest ? "Đang dọn..." : "Dọn Dữ Liệu Test"}</span>
          </button>
          {onOpenSettings && (
            <button
              className="btn-settings"
              onClick={onOpenSettings}
              title="Cài đặt Cache & Phí thẩm định"
            >
              <Settings size={16} />
              <span>Cài Đặt Cache</span>
            </button>
          )}
        </div>
      </div>

      {/* KPI Stats Banner */}
      <div className="dd-history-stats-grid">
        <div className="stat-card">
          <div className="stat-label">Tổng Số Hồ Sơ Đã Lập</div>
          <div className="stat-value">{stats.total}</div>
          <div className="stat-sub">Toàn bộ hồ sơ đã lưu trữ</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Hồ Sơ Tái Sử Dụng Cache</div>
          <div className="stat-value text-green">
            <Zap size={20} className="inline-icon" /> {stats.cachedCount}
          </div>
          <div className="stat-sub">Tiết kiệm 100% token LLM</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Cơ Chế Smart Cache</div>
          <div className="stat-value text-blue">
            {stats.cacheEnabled ? `${stats.cacheTtl}h Hiệu lực` : "Đang Tắt"}
          </div>
          <div className="stat-sub">
            {stats.cacheEnabled ? "Tự động kích hoạt khi thẩm định lại" : "Chạy agent mới mọi lúc"}
          </div>
        </div>
      </div>

      {/* Toolbar: Scopes + Filters */}
      <div className="dd-history-toolbar">
        <div className="scope-tabs">
          <button
            className={`scope-tab ${scope === "all" ? "active" : ""}`}
            onClick={() => setScope("all")}
          >
            <Users size={15} />
            <span>Tất Cả Thẩm Định Hệ Thống</span>
          </button>
          <button
            className={`scope-tab ${scope === "user" ? "active" : ""}`}
            onClick={() => setScope("user")}
          >
            <User size={15} />
            <span>Hồ Sơ Của Tôi</span>
          </button>
        </div>

        <div className="filters-row">
          <div className="search-input-box">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              placeholder="Tìm theo tên BĐS, phường, quận..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button className="clear-btn" onClick={() => setSearchQuery("")}>×</button>
            )}
          </div>

          <div className="filter-select-box">
            <MapPin size={15} className="select-icon" />
            <select
              value={districtFilter}
              onChange={(e) => setDistrictFilter(e.target.value)}
            >
              <option value="all">Tất cả Quận / Huyện</option>
              {uniqueDistricts.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>

          <div className="filter-select-box">
            <Filter size={15} className="select-icon" />
            <select
              value={verdictFilter}
              onChange={(e) => setVerdictFilter(e.target.value)}
            >
              <option value="all">Tất cả Kết luận</option>
              <option value="STRONGLY_RECOMMENDED">Khuyến nghị mạnh (An toàn)</option>
              <option value="PROCEED_WITH_CAUTION">Cần thận trọng (Đàm phán)</option>
              <option value="HIGH_RISK_AVOID">Rủi ro cao (Cân nhắc tránh)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content: Cards Grid */}
      {loading ? (
        <div className="dd-history-loading">
          <div className="spinner"></div>
          <p>Đang tải danh sách hồ sơ thẩm định...</p>
        </div>
      ) : filteredList.length === 0 ? (
        <div className="dd-history-empty">
          <FileText size={48} className="empty-icon" />
          <h3>Không tìm thấy hồ sơ thẩm định nào</h3>
          <p>
            {searchQuery || districtFilter !== "all" || verdictFilter !== "all"
              ? "Hãy thử điều chỉnh lại từ khóa hoặc xóa bớt bộ lọc."
              : scope === "user"
              ? "Bạn chưa thực hiện thẩm định BĐS nào. Hãy quay về khung chat hoặc chọn BĐS để bắt đầu thẩm định!"
              : "Hệ thống chưa ghi nhận hồ sơ thẩm định nào."}
          </p>
        </div>
      ) : (
        <div className="dd-history-grid">
          {filteredList.map((item, index) => {
            if (!item) return null;
            const badge = getVerdictBadge(item.verdict);
            const BadgeIcon = badge?.icon;
            const isOpening = openingTaskId === item.task_id;

            return (
              <div
                key={item.task_id || `item-${index}`}
                className="dd-history-card"
                onClick={() => handleOpenDetail(item)}
              >
                {/* Card Top: Badges */}
                <div className="card-top-row">
                  <div className={`verdict-pill ${badge?.className || "badge-gray"}`}>
                    {BadgeIcon && <BadgeIcon size={14} />}
                    <span>{badge?.label || "Đã thẩm định"}</span>
                  </div>

                  <div className="right-badges">
                    {item.is_cached && (
                      <span className="badge-cache" title="Kết quả được tái sử dụng từ Cache 48h (Tiết kiệm chi phí)">
                        <Zap size={12} /> Cache {stats.cacheTtl}h
                      </span>
                    )}
                    {item.overall_score !== null && item.overall_score !== undefined && (
                      <span className="badge-score">
                        Điểm: <strong>{item.overall_score}</strong>/10
                      </span>
                    )}
                  </div>
                </div>

                {/* Property Title */}
                <h4 className="card-title" title={item.property_title}>
                  {item.property_title}
                </h4>

                {/* Meta details */}
                <div className="card-meta-list">
                  <div className="meta-item">
                    <MapPin size={14} className="icon-dim" />
                    <span>
                      {item.ward ? `${item.ward}, ` : ""}{item.district || "TP. Đà Nẵng"}
                    </span>
                  </div>
                  <div className="meta-row-two">
                    <span className="price-tag">{formatPriceVND(item.property_price)}</span>
                    <span className="area-tag">{item.area_m2} m²</span>
                  </div>
                </div>

                {/* Card Footer: Date & Actions */}
                <div className="card-footer">
                  <div className="card-date">
                    <Calendar size={13} />
                    <span>{formatDate(item.created_at)}</span>
                  </div>

                  <div className="card-actions-group">
                    <button
                      className="btn-clear-single-cache"
                      onClick={(e) => handleDeleteHistoryItem(e, item)}
                      disabled={deletingTaskId === item.task_id}
                      title="Xóa vĩnh viễn hồ sơ thẩm định này khỏi lịch sử"
                    >
                      {deletingTaskId === item.task_id ? (
                        <RotateCw size={13} className="spin" />
                      ) : (
                        <Trash2 size={13} />
                      )}
                    </button>
                    <button
                      className="btn-view-report"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenDetail(item);
                      }}
                      disabled={isOpening}
                    >
                      {isOpening ? (
                        <span>Đang mở...</span>
                      ) : (
                        <>
                          <ExternalLink size={13} />
                          <span>Xem Báo Cáo</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
