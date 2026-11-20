// frontend/src/components/DueDiligenceSettingsModal.jsx
import React, { useState, useEffect } from "react";
import {
  Settings,
  X,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Trash2,
  Clock,
  Coins,
  Zap,
  Info
} from "lucide-react";
import "./DueDiligenceSettingsModal.css";

export default function DueDiligenceSettingsModal({
  isOpen,
  onClose,
  API_BASE = "",
  onSettingsSaved = null
}) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const [cacheEnabled, setCacheEnabled] = useState(true);
  const [cacheTtlHours, setCacheTtlHours] = useState(48);
  const [cacheHitCostVnd, setCacheHitCostVnd] = useState(0);
  const [allowForceRefresh, setAllowForceRefresh] = useState(true);

  useEffect(() => {
    if (isOpen) {
      fetchSettings();
    }
  }, [isOpen]);

  const fetchSettings = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/due-diligence/settings`);
      const data = await res.json();
      if (res.ok && data.success && data.settings) {
        setCacheEnabled(Boolean(data.settings.cache_enabled));
        setCacheTtlHours(Number(data.settings.cache_ttl_hours) || 48);
        setCacheHitCostVnd(Number(data.settings.cache_hit_cost_vnd) || 0);
        setAllowForceRefresh(data.settings.allow_force_refresh !== false);
      }
    } catch (e) {
      setFeedback({ type: "error", message: "Không thể tải cấu hình từ máy chủ: " + e.message });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setFeedback(null);

    const ttlNum = Number(cacheTtlHours);
    if (isNaN(ttlNum) || ttlNum < 1 || ttlNum > 720) {
      setFeedback({ type: "error", message: "Thời gian hiệu lực Cache phải từ 1 đến 720 giờ (tối đa 30 ngày)." });
      setSaving(false);
      return;
    }

    const costNum = Number(cacheHitCostVnd);
    if (isNaN(costNum) || costNum < 0) {
      setFeedback({ type: "error", message: "Phí Cache Hit không được là số âm." });
      setSaving(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/due-diligence/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cache_enabled: cacheEnabled,
          cache_ttl_hours: ttlNum,
          cache_hit_cost_vnd: costNum,
          allow_force_refresh: allowForceRefresh
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setFeedback({ type: "success", message: "Đã cập nhật cài đặt thẩm định & cache thành công!" });
        if (onSettingsSaved) {
          onSettingsSaved(data.settings);
        }
        setTimeout(() => {
          onClose();
        }, 1200);
      } else {
        throw new Error(data.detail || "Cập nhật thất bại");
      }
    } catch (err) {
      setFeedback({ type: "error", message: "Lỗi lưu cài đặt: " + err.message });
    } finally {
      setSaving(false);
    }
  };

  const handleClearAllCache = async () => {
    if (!window.confirm("Bạn có chắc chắn muốn XÓA TOÀN BỘ CACHE thẩm định? Mọi BĐS được thẩm định tiếp theo sẽ chạy lại toàn bộ quy trình AI.")) {
      return;
    }
    setClearing(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/due-diligence/cache/clear`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setFeedback({
          type: "success",
          message: `Đã dọn dẹp ${data.cleared_count} hồ sơ cache. Toàn bộ BĐS sẽ được thẩm định lại từ đầu khi có yêu cầu mới.`
        });
        if (onSettingsSaved) onSettingsSaved();
      } else {
        throw new Error(data.detail || "Không thể dọn dẹp cache");
      }
    } catch (err) {
      setFeedback({ type: "error", message: "Lỗi dọn cache: " + err.message });
    } finally {
      setClearing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="dd-settings-overlay">
      <div className="dd-settings-modal">
        <div className="dd-settings-header">
          <div className="header-title">
            <Settings size={22} className="icon-blue" />
            <div>
              <h3>Cài Đặt Thẩm Định & Cache Linh Động</h3>
              <p className="subtitle">Cấu hình thời gian lưu trữ, điều kiện cache và chi phí thẩm định lại</p>
            </div>
          </div>
          <button className="btn-close" onClick={onClose} aria-label="Đóng">
            <X size={18} />
          </button>
        </div>

        {feedback && (
          <div className={`dd-settings-alert ${feedback.type}`}>
            {feedback.type === "success" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
            <span>{feedback.message}</span>
          </div>
        )}

        {loading ? (
          <div className="dd-settings-loading">
            <div className="spinner"></div>
            <span>Đang tải cài đặt từ máy chủ...</span>
          </div>
        ) : (
          <form onSubmit={handleSave} className="dd-settings-form">
            {/* Toggle Bật / Tắt Cache */}
            <div className="form-group toggle-group">
              <div className="toggle-label">
                <div className="title-with-icon">
                  <Zap size={18} className="icon-amber" />
                  <strong>Bật cơ chế Cache Thẩm định</strong>
                </div>
                <span className="desc">
                  Tự động tái sử dụng hồ sơ Dossier đã có khi cùng một BĐS được thẩm định nhiều lần trong thời gian hiệu lực.
                </span>
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={cacheEnabled}
                  onChange={(e) => setCacheEnabled(e.target.checked)}
                />
                <span className="slider round"></span>
              </label>
            </div>

            {/* Thời gian hiệu lực Cache (TTL Hours) */}
            <div className="form-group">
              <label className="input-label">
                <Clock size={16} className="icon-blue" />
                <span>Thời gian hiệu lực Cache (Giờ)</span>
              </label>
              <div className="ttl-input-wrapper">
                <input
                  type="number"
                  min="1"
                  max="720"
                  value={cacheTtlHours}
                  onChange={(e) => setCacheTtlHours(e.target.value)}
                  className="number-input"
                  required
                />
                <span className="unit-tag">Giờ ({Number(cacheTtlHours) >= 24 ? `${(Number(cacheTtlHours) / 24).toFixed(1)} ngày` : `${cacheTtlHours}h`})</span>
              </div>
              <div className="preset-buttons">
                <button type="button" className={`preset-btn ${cacheTtlHours === 12 ? "active" : ""}`} onClick={() => setCacheTtlHours(12)}>12 Giờ</button>
                <button type="button" className={`preset-btn ${cacheTtlHours === 24 ? "active" : ""}`} onClick={() => setCacheTtlHours(24)}>24 Giờ</button>
                <button type="button" className={`preset-btn ${cacheTtlHours === 48 ? "active" : ""}`} onClick={() => setCacheTtlHours(48)}>48 Giờ (Khuyên dùng)</button>
                <button type="button" className={`preset-btn ${cacheTtlHours === 72 ? "active" : ""}`} onClick={() => setCacheTtlHours(72)}>72 Giờ (3 ngày)</button>
                <button type="button" className={`preset-btn ${cacheTtlHours === 168 ? "active" : ""}`} onClick={() => setCacheTtlHours(168)}>7 Ngày</button>
              </div>
            </div>

            {/* Phí khi Cache Hit */}
            <div className="form-group">
              <label className="input-label">
                <Coins size={16} className="icon-green" />
                <span>Phí dịch vụ khi tái sử dụng Cache (VNĐ)</span>
              </label>
              <div className="ttl-input-wrapper">
                <input
                  type="number"
                  min="0"
                  step="1000"
                  value={cacheHitCostVnd}
                  onChange={(e) => setCacheHitCostVnd(e.target.value)}
                  className="number-input"
                  required
                />
                <span className="unit-tag">{Number(cacheHitCostVnd) === 0 ? "Miễn phí hoàn toàn (0 ₫)" : `${Number(cacheHitCostVnd).toLocaleString("vi-VN")} ₫`}</span>
              </div>
              <p className="field-hint">
                <Info size={13} /> Khuyên dùng 0 ₫ để tối đa hóa trải nghiệm người dùng và tiết kiệm 100% chi phí chạy lại.
              </p>
            </div>

            {/* Cho phép Force Refresh */}
            <div className="form-group toggle-group">
              <div className="toggle-label">
                <div className="title-with-icon">
                  <RotateCcw size={16} />
                  <strong>Cho phép người dùng bấm "Thẩm định lại mới"</strong>
                </div>
                <span className="desc">
                  Hiển thị nút cho phép user tùy chọn chạy lại từ đầu nếu muốn thay đổi thông số vốn/vay cá nhân.
                </span>
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={allowForceRefresh}
                  onChange={(e) => setAllowForceRefresh(e.target.checked)}
                />
                <span className="slider round"></span>
              </label>
            </div>

            {/* Danger Zone: Dọn sạch cache */}
            <div className="danger-zone">
              <div className="danger-info">
                <strong>Khu vực Quản trị Bộ Nhớ</strong>
                <p>Xóa tất cả kết quả cache để ép buộc hệ thống cập nhật lại các biến động giá, pháp lý và lãi suất mới nhất.</p>
              </div>
              <button
                type="button"
                className="btn-danger"
                onClick={handleClearAllCache}
                disabled={clearing}
              >
                <Trash2 size={15} />
                <span>{clearing ? "Đang xóa..." : "Xóa Toàn Bộ Cache Thẩm Định"}</span>
              </button>
            </div>

            <div className="dd-settings-actions">
              <button type="button" className="btn-cancel" onClick={onClose} disabled={saving}>
                Hủy bỏ
              </button>
              <button type="submit" className="btn-save" disabled={saving}>
                {saving ? "Đang lưu..." : "Lưu Cài Đặt"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
