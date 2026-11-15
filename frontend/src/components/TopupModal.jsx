import React, { useState, useEffect } from "react";
import {
  Wallet,
  CreditCard,
  CheckCircle2,
  Zap,
  Clock,
  X,
  QrCode,
  ShieldCheck,
  Copy,
  Sparkles,
  ArrowRight,
  RefreshCw,
  Gift
} from "lucide-react";

const PACKAGES = [
  { id: "pkg_5k", amount: 5000, label: "Gói Khởi Động", desc: "~15-30 lượt tương tác", popular: false },
  { id: "pkg_10k", amount: 10000, label: "Gói Phổ Biến", desc: "~40-80 lượt tương tác", popular: true },
  { id: "pkg_20k", amount: 20000, label: "Gói Tiết Kiệm", desc: "~80-150 lượt tương tác", popular: false },
  { id: "pkg_50k", amount: 50000, label: "Gói Nâng Cao", desc: "Thoải mái tra cứu & thẩm định HĐ", popular: false },
  { id: "pkg_100k", amount: 100000, label: "Gói Không Giới Hạn", desc: "Sử dụng tối đa mọi tính năng", popular: false }
];

export default function TopupModal({
  isOpen,
  onClose,
  userId,
  wallet,
  onTopupSuccess,
  API_BASE = ""
}) {
  const [selectedAmount, setSelectedAmount] = useState(10000);
  const [customAmount, setCustomAmount] = useState("");
  const [activeTab, setActiveTab] = useState("packages"); // "packages" | "transactions"
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loadingTx, setLoadingTx] = useState(false);
  const [copiedField, setCopiedField] = useState(null);

  // Khi modal mở, tải lịch sử giao dịch nếu chọn tab lịch sử
  useEffect(() => {
    if (isOpen && activeTab === "transactions") {
      fetchTransactions();
    }
  }, [isOpen, activeTab]);

  const fetchTransactions = async () => {
    setLoadingTx(true);
    try {
      const res = await fetch(`${API_BASE}/api/user/wallet/transactions?user_id=${encodeURIComponent(userId)}&limit=25`);
      const data = await res.json();
      if (Array.isArray(data)) {
        setTransactions(data);
      }
    } catch (err) {
      console.error("Lỗi lấy lịch sử giao dịch:", err);
    } finally {
      setLoadingTx(false);
    }
  };

  if (!isOpen) return null;

  const currentAmount = customAmount ? Number(customAmount) : selectedAmount;

  const handleSelectPackage = (pkg) => {
    setSelectedAmount(pkg.amount);
    setCustomAmount("");
    setFeedback(null);
  };

  const handleCustomAmountChange = (e) => {
    const val = e.target.value.replace(/\D/g, "");
    setCustomAmount(val);
    if (val) {
      setSelectedAmount(Number(val));
    }
    setFeedback(null);
  };

  const handleCopy = (text, fieldName) => {
    navigator.clipboard?.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleMockTopup = async () => {
    if (currentAmount <= 0) {
      setFeedback({ type: "error", message: "Số tiền nạp tối thiểu là 1.000 ₫" });
      return;
    }

    setLoading(true);
    setFeedback(null);

    try {
      const res = await fetch(`${API_BASE}/api/user/wallet/topup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          amount_vnd: currentAmount,
          description: `Nạp tiền gói ${currentAmount.toLocaleString("vi-VN")} ₫ (Mock Payment)`
        })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        setFeedback({
          type: "success",
          message: `Nạp thành công +${currentAmount.toLocaleString("vi-VN")} ₫ vào ví! Số dư mới: ${Math.round(data.wallet.balance_vnd).toLocaleString("vi-VN")} ₫.`
        });
        if (onTopupSuccess) {
          onTopupSuccess(data.wallet);
        }
        setTimeout(() => {
          onClose();
        }, 1600);
      } else {
        setFeedback({ type: "error", message: data.detail || "Nạp tiền thất bại, vui lòng thử lại!" });
      }
    } catch (err) {
      setFeedback({ type: "error", message: "Lỗi kết nối máy chủ: " + err.message });
    } finally {
      setLoading(false);
    }
  };

  const formatVND = (num) => {
    if (num === null || num === undefined) return "0 ₫";
    return Math.round(Number(num)).toLocaleString("vi-VN") + " ₫";
  };

  const transferSyntax = `NAP ${userId.slice(0, 8).toUpperCase()}`;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="topup-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Header Modal */}
        <div className="topup-modal-header">
          <div className="topup-header-title-box">
            <div className="topup-icon-badge">
              <Wallet size={22} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <h3 className="topup-title" style={{ margin: 0 }}>Ví Tiêu Dùng Trợ Lý AI</h3>
                <span className="badge-modal-tier" title="Hạng thành viên của bạn">
                  ⭐ {wallet?.group_name || "Người dùng thường"}
                </span>
              </div>
              <p className="topup-subtitle">
                ID Khách: <code>{userId.slice(0, 14)}...</code>
              </p>
            </div>
          </div>
          <button className="btn-close-modal" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {/* Thẻ trạng thái ví người dùng */}
        <div className="wallet-snapshot-banner">
          <div className="snapshot-card">
            <span className="snapshot-label">Số Dư Tiền Nạp</span>
            <div className="snapshot-val highlight-blue">
              {formatVND(wallet?.balance_vnd)}
            </div>
            <span className="snapshot-sub">Số dư dùng khi vượt hạn mức free</span>
          </div>

          <div className="snapshot-card">
            <span className="snapshot-label">Hạn Mức Free Hôm Nay</span>
            <div className="snapshot-val highlight-green">
              {formatVND(wallet?.daily_free_remaining_vnd)}
            </div>
            <span className="snapshot-sub">
              Tặng sẵn {formatVND(wallet?.daily_free_limit_vnd || 5000)}/ngày ({wallet?.group_name || "Tiêu chuẩn"})
            </span>
          </div>
        </div>

        {/* Thông báo cơ chế ngân sách */}
        <div className="daily-quota-banner">
          <Gift size={16} color="#059669" />
          <span>
            <b>Chính sách nhóm {wallet?.group_name || "Tiêu chuẩn"}:</b> Mỗi ngày bạn nhận được{" "}
            <b>{formatVND(wallet?.daily_free_limit_vnd || 5000)} miễn phí</b>. Khi dùng hết hạn mức trong ngày, hệ thống sẽ tự động trừ vào số dư ví nạp của bạn.
          </span>
        </div>

        {/* Tab switcher: Chọn gói nạp vs Lịch sử giao dịch */}
        <div className="topup-tabs-bar">
          <button
            className={`topup-tab-btn ${activeTab === "packages" ? "active" : ""}`}
            onClick={() => setActiveTab("packages")}
          >
            <Zap size={14} /> Chọn Gói Nạp Tiền
          </button>
          <button
            className={`topup-tab-btn ${activeTab === "transactions" ? "active" : ""}`}
            onClick={() => setActiveTab("transactions")}
          >
            <Clock size={14} /> Lịch Sử Giao Dịch
          </button>
        </div>

        {/* Feedback message */}
        {feedback && (
          <div className={`topup-feedback-alert ${feedback.type}`}>
            {feedback.type === "success" ? <CheckCircle2 size={16} /> : <X size={16} />}
            <span>{feedback.message}</span>
          </div>
        )}

        {/* TAB 1: CHỌN GÓI NẠP & THANH TOÁN MOCK */}
        {activeTab === "packages" && (
          <div className="topup-packages-content">
            <label className="section-small-title">1. Chọn gói nạp tiện lợi:</label>
            <div className="packages-grid">
              {PACKAGES.map((pkg) => {
                const isSelected = !customAmount && selectedAmount === pkg.amount;
                return (
                  <div
                    key={pkg.id}
                    className={`package-card ${isSelected ? "selected" : ""} ${pkg.popular ? "popular" : ""}`}
                    onClick={() => handleSelectPackage(pkg)}
                  >
                    {pkg.popular && <span className="package-popular-badge">Khuyên dùng</span>}
                    <div className="package-amount">{pkg.amount.toLocaleString("vi-VN")} ₫</div>
                    <div className="package-label">{pkg.label}</div>
                    <div className="package-desc">{pkg.desc}</div>
                  </div>
                );
              })}
            </div>

            {/* Hoặc nhập số tiền tùy ý */}
            <div className="custom-amount-row">
              <label>Hoặc nhập số tiền khác:</label>
              <div className="custom-input-wrapper">
                <input
                  type="text"
                  placeholder="Ví dụ: 15.000"
                  value={customAmount ? Number(customAmount).toLocaleString("vi-VN") : ""}
                  onChange={handleCustomAmountChange}
                />
                <span className="currency-unit">VND</span>
              </div>
            </div>

            {/* Mock VietQR & Hướng dẫn thanh toán */}
            <div className="vietqr-mock-section">
              <div className="vietqr-header">
                <QrCode size={16} color="#2563eb" />
                <span className="vietqr-title">Phương Thức Thanh Toán (Mock VietQR / Chuyển Khoản)</span>
              </div>

              <div className="vietqr-body">
                {/* Giả lập khung mã QR */}
                <div className="mock-qr-code-box">
                  <div className="qr-visual">
                    <QrCode size={84} color="#1e293b" />
                    <span className="qr-badge-mock">MOCK QR</span>
                  </div>
                  <span className="qr-note">Quét mã để nạp nhanh</span>
                </div>

                {/* Thông tin chuyển khoản */}
                <div className="transfer-info-list">
                  <div className="transfer-item">
                    <span className="transfer-label">Ngân hàng:</span>
                    <span className="transfer-value">MBBank (Ngân hàng Quân Đội)</span>
                  </div>

                  <div className="transfer-item">
                    <span className="transfer-label">Số tài khoản:</span>
                    <div className="transfer-copy-group">
                      <span className="transfer-value mono">0905 888 999</span>
                      <button
                        className="btn-copy-small"
                        onClick={() => handleCopy("0905888999", "stk")}
                        title="Sao chép số tài khoản"
                      >
                        <Copy size={12} />
                        {copiedField === "stk" ? "Đã chép" : "Chép"}
                      </button>
                    </div>
                  </div>

                  <div className="transfer-item">
                    <span className="transfer-label">Số tiền:</span>
                    <span className="transfer-value text-blue">
                      {currentAmount > 0 ? currentAmount.toLocaleString("vi-VN") + " ₫" : "0 ₫"}
                    </span>
                  </div>

                  <div className="transfer-item">
                    <span className="transfer-label">Nội dung CK:</span>
                    <div className="transfer-copy-group">
                      <span className="transfer-value mono">{transferSyntax}</span>
                      <button
                        className="btn-copy-small"
                        onClick={() => handleCopy(transferSyntax, "syntax")}
                        title="Sao chép nội dung"
                      >
                        <Copy size={12} />
                        {copiedField === "syntax" ? "Đã chép" : "Chép"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Nút nạp 1-click test */}
              <div className="mock-action-footer">
                <button
                  className="btn-mock-oneclick"
                  onClick={handleMockTopup}
                  disabled={loading || currentAmount <= 0}
                >
                  {loading ? (
                    <>
                      <RefreshCw size={16} className="spin-icon" /> Đang cộng tiền vào ví...
                    </>
                  ) : (
                    <>
                      <Zap size={16} /> Nạp Thử Nghiệm Ngay (+{currentAmount.toLocaleString("vi-VN")} ₫)
                    </>
                  )}
                </button>
                <span className="mock-sub-hint">
                  Hệ thống môi trường phát triển: Bấm nút trên để cộng tiền vào tài khoản ngay lập tức mà không cần chuyển khoản thực tế.
                </span>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: LỊCH SỬ GIAO DỊCH */}
        {activeTab === "transactions" && (
          <div className="topup-transactions-content">
            <div className="tx-header-row">
              <span className="section-small-title">Lịch sử nạp tiền & khấu trừ chi phí:</span>
              <button className="btn-refresh-tx" onClick={fetchTransactions} disabled={loadingTx}>
                <RefreshCw size={13} className={loadingTx ? "spin-icon" : ""} />
                Làm mới
              </button>
            </div>

            <div className="tx-table-container">
              {loadingTx ? (
                <div className="tx-loading-state">Đang tải lịch sử giao dịch...</div>
              ) : transactions.length === 0 ? (
                <div className="tx-empty-state">Chưa có giao dịch nào được ghi nhận.</div>
              ) : (
                <table className="tx-table">
                  <thead>
                    <tr>
                      <th>Thời Gian</th>
                      <th>Loại Giao Dịch</th>
                      <th style={{ textAlign: "right" }}>Số Tiền</th>
                      <th>Nội Dung</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((tx) => {
                      const isTopup = tx.transaction_type === "TOPUP";
                      return (
                        <tr key={tx.transaction_id}>
                          <td style={{ fontSize: "11.5px", color: "#64748b", whiteSpace: "nowrap" }}>
                            {tx.created_at ? new Date(tx.created_at).toLocaleString("vi-VN") : "-"}
                          </td>
                          <td>
                            <span className={`tx-type-pill ${isTopup ? "topup" : "charge"}`}>
                              {isTopup ? "Nạp Tiền" : "Khấu Trừ AI"}
                            </span>
                          </td>
                          <td
                            style={{
                              textAlign: "right",
                              fontWeight: "700",
                              color: isTopup ? "#16a34a" : "#dc2626"
                            }}
                          >
                            {isTopup ? `+${formatVND(tx.amount_vnd)}` : formatVND(tx.amount_vnd)}
                          </td>
                          <td style={{ fontSize: "12px", color: "#334155" }}>
                            {tx.description}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
