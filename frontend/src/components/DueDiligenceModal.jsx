// frontend/src/components/DueDiligenceModal.jsx
import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import {
  Scale,
  ShieldCheck,
  AlertTriangle,
  TrendingUp,
  Compass,
  DollarSign,
  Calculator,
  CloudRain,
  CheckCircle2,
  Flame,
  Award,
  Search,
  Copy,
  Check,
  X,
  Loader2,
  RotateCw,
  Droplets,
  MapPin,
  Maximize2,
  Home,
  ShieldAlert,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Percent,
  Layers,
  Building2,
  Handshake,
  AlertCircle,
  Wallet
} from "lucide-react";
import "./DueDiligenceModal.css";

const formatVND = (val) => {
  if (val === undefined || val === null || isNaN(val)) return "0 VNĐ";
  return Number(val).toLocaleString("vi-VN") + " VNĐ";
};

const formatShortVND = (val) => {
  if (!val || isNaN(val)) return "0 đ";
  if (val >= 1_000_000_000) {
    return (val / 1_000_000_000).toFixed(2).replace(/\.00$/, "") + " Tỷ";
  }
  if (val >= 1_000_000) {
    return (val / 1_000_000).toFixed(1).replace(/\.0$/, "") + " Triệu";
  }
  return Number(val).toLocaleString("vi-VN") + " đ";
};

const getStageLabel = (stage) => {
  switch (stage) {
    case "planning":
      return "Đang thiết lập kế hoạch và phân rã mục tiêu thẩm định...";
    case "investigating":
      return "Đang điều tra đa nguồn: Pháp lý, Định giá, Thủy văn & Tài chính...";
    case "critiquing":
      return "Đang phản biện rủi ro độc lập (Devil's Advocate Critic)...";
    case "synthesizing":
      return "Đang tổng hợp Dossier và tính toán điểm số tổng hợp...";
    case "completed":
      return "Thẩm định hoàn tất! Báo cáo Dossier đã sẵn sàng.";
    case "failed":
      return "Quá trình thẩm định gặp sự cố.";
    default:
      return "Hệ thống đang chuẩn bị...";
  }
};

export default function DueDiligenceModal({
  isOpen,
  onClose,
  property,
  userId,
  userWallet,
  API_BASE = "",
  onOpenTopup,
  onRequireTopup,
  onWalletUpdate
}) {
  const [objective, setObjective] = useState("residential");
  const [equityRatio, setEquityRatio] = useState(0.7);
  const [isConfigCollapsed, setIsConfigCollapsed] = useState(false);

  // Execution & Stream State
  const [taskId, setTaskId] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentStage, setCurrentStage] = useState("idle");
  const [progress, setProgress] = useState(0);
  const [stageDescription, setStageDescription] = useState("");
  const [errorMessage, setErrorMessage] = useState(null);
  const [isQuotaError, setIsQuotaError] = useState(false);

  // Result & Dossier
  const [dossier, setDossier] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [copiedMarkdown, setCopiedMarkdown] = useState(false);

  const eventSourceRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const abortControllerRef = useRef(null);
  const failedPollsRef = useRef(0);

  const prevPropIdRef = useRef(property?.id);

  // Reset or initialize when modal opens with a new property or closes
  useEffect(() => {
    const isNewProp = prevPropIdRef.current !== property?.id;
    prevPropIdRef.current = property?.id;

    if (!isOpen || isNewProp) {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      failedPollsRef.current = 0;

      // Reset all internal states cleanly
      setDossier(null);
      setTaskId(null);
      setIsAnalyzing(false);
      setCurrentStage("idle");
      setProgress(0);
      setStageDescription("");
      setErrorMessage(null);
      setIsQuotaError(false);
      setIsConfigCollapsed(false);
      setActiveTab("overview");
    }
  }, [isOpen, property?.id]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      failedPollsRef.current = 0;
    };
  }, []);

  if (!isOpen || !property) return null;

  const propertyPrice = Number(property.price) || 0;
  const areaM2 = Number(property.area_m2 || property.area || 0);
  const equityCapital = Math.round(propertyPrice * equityRatio);
  const loanAmount = Math.max(0, propertyPrice - equityCapital);

  // Month 1 repayment calculation (20 years, 8.5% p.a., reducing balance)
  const tenureMonths = 240;
  const monthlyPrincipal = loanAmount / tenureMonths;
  const month1Interest = loanAmount * (0.085 / 12);
  const estimatedMonth1Payment = Math.round(monthlyPrincipal + month1Interest);

  const handleStartAnalysis = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    setIsAnalyzing(true);
    setErrorMessage(null);
    setIsQuotaError(false);
    setCurrentStage("planning");
    setProgress(15);
    setStageDescription(getStageLabel("planning"));
    setDossier(null);
    setIsConfigCollapsed(true);

    const propId = property.id || "dn_prop_selected";

    try {
      const res = await fetch(`${API_BASE}/api/due-diligence`, {
        method: "POST",
        signal: abortController.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          property_id: propId,
          property_title: property.title,
          property_price: propertyPrice,
          area_m2: areaM2 || 100.0,
          district: property.district || "Hải Châu",
          ward: property.ward || "",
          investment_objective: objective,
          equity_ratio: equityRatio,
          equity_capital_vnd: equityCapital,
          loan_amount_vnd: loanAmount,
          user_id: userId
        })
      });

      if (res.status === 402) {
        setIsQuotaError(true);
        throw new Error("Số dư tài khoản không đủ để thực hiện thẩm định chuyên sâu (phí 150 VNĐ). Vui lòng nạp thêm tiền.");
      }

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.error || "Không thể khởi tạo tác vụ thẩm định");
      }

      const newTaskId = data.task_id;
      setTaskId(newTaskId);

      // Trigger wallet refresh if caller provided a callback
      if (onWalletUpdate && userId) {
        fetch(`${API_BASE}/api/wallet/${userId}`)
          .then((r) => r.json())
          .then((w) => onWalletUpdate(w))
          .catch(() => {});
      }

      subscribeToStream(newTaskId);
    } catch (err) {
      if (err.name === "AbortError") {
        return;
      }
      setIsAnalyzing(false);
      setCurrentStage("failed");
      setErrorMessage(err.message || "Đã xảy ra lỗi khi khởi chạy thẩm định.");
    } finally {
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null;
      }
    }
  };

  const subscribeToStream = (tid) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    let isDone = false;
    const es = new EventSource(`${API_BASE}/api/due-diligence/${tid}/stream`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      if (event.data === "[DONE]") {
        isDone = true;
        es.close();
        eventSourceRef.current = null;
        return;
      }

      try {
        const payload = JSON.parse(event.data);
        if (payload.status) setCurrentStage(payload.status);
        if (typeof payload.progress === "number") {
          setProgress((prev) => Math.max(prev, payload.progress));
        }
        if (payload.stage) setStageDescription(getStageLabel(payload.stage));

        if (payload.status === "completed" || payload.type === "completed") {
          isDone = true;
          es.close();
          eventSourceRef.current = null;
          setIsAnalyzing(false);
          setProgress(100);
          const finalDossier = payload.dossier || payload.result;
          if (finalDossier) setDossier(finalDossier);

          // Update user wallet balance if callback provided
          if (onWalletUpdate && userId) {
            fetch(`${API_BASE}/api/wallet/${userId}`)
              .then((r) => r.json())
              .then((w) => onWalletUpdate(w))
              .catch(() => {});
          }
        } else if (payload.status === "failed" || payload.type === "error") {
          isDone = true;
          es.close();
          eventSourceRef.current = null;
          setIsAnalyzing(false);
          setErrorMessage(payload.error || "Thẩm định thất bại do lỗi phân tích.");
        }
      } catch (e) {
        console.warn("Lỗi parse SSE event:", e);
      }
    };

    es.onerror = () => {
      es.close();
      eventSourceRef.current = null;
      if (!isDone) {
        pollTaskStatus(tid);
      }
    };
  };

  const pollTaskStatus = (tid) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    failedPollsRef.current = 0;

    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/due-diligence/${tid}`);
        if (!res.ok) {
          failedPollsRef.current += 1;
          if (failedPollsRef.current >= 10) {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsAnalyzing(false);
            setCurrentStage("failed");
            setErrorMessage("Không thể kết nối đến máy chủ để cập nhật tiến độ thẩm định (đã thử lại 10 lần thất bại).");
          }
          return;
        }

        // Reset failure counter on successful response
        failedPollsRef.current = 0;
        const data = await res.json();

        if (data.status) setCurrentStage(data.status);
        if (typeof data.progress === "number") {
          setProgress((prev) => Math.max(prev, data.progress));
        }
        if (data.stage) setStageDescription(getStageLabel(data.stage));

        if (data.status === "completed") {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setIsAnalyzing(false);
          setProgress(100);
          if (data.dossier || data.result) {
            setDossier(data.dossier || data.result);
          }
          if (onWalletUpdate && userId) {
            fetch(`${API_BASE}/api/wallet/${userId}`)
              .then((r) => r.json())
              .then((w) => onWalletUpdate(w))
              .catch(() => {});
          }
        } else if (data.status === "failed") {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setIsAnalyzing(false);
          setErrorMessage(data.error_message || data.error || "Thẩm định thất bại trong quá trình phân tích.");
        }
      } catch (err) {
        failedPollsRef.current += 1;
        console.warn("Polling fallback error:", err);
        if (failedPollsRef.current >= 10) {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setIsAnalyzing(false);
          setCurrentStage("failed");
          setErrorMessage("Không thể kết nối đến máy chủ để cập nhật tiến độ thẩm định (đã thử lại 10 lần thất bại).");
        }
      }
    }, 2000);
  };

  const handleCopyMarkdown = () => {
    if (!dossier?.full_markdown_report) return;
    navigator.clipboard
      .writeText(dossier.full_markdown_report)
      .then(() => {
        setCopiedMarkdown(true);
        setTimeout(() => setCopiedMarkdown(false), 2000);
      })
      .catch((err) => {
        console.warn("Clipboard copy failed:", err);
      });
  };

  const handleOpenTopupModal = () => {
    if (onClose) onClose();
    if (onOpenTopup) onOpenTopup();
    else if (onRequireTopup) onRequireTopup();
  };

  // Helper for Stepper stages
  const getStepStatus = (stepIdx) => {
    if (currentStage === "completed" || dossier) return "completed";
    if (currentStage === "failed") return "pending";

    const stageOrder = ["planning", "investigating", "critiquing", "synthesizing", "completed"];
    const currentIdx = stageOrder.indexOf(currentStage);

    if (currentIdx > stepIdx) return "completed";
    if (currentIdx === stepIdx) return "active";
    return "pending";
  };

  // Scorecard SVG circle math
  const score = dossier?.overall_score ?? 0;
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (Math.min(100, Math.max(0, score)) / 100) * circumference;

  // Synthesized verdict calculation with strict priority to dossier?.verdict
  const verdict =
    dossier?.verdict ||
    (score >= 80 ? "STRONGLY_RECOMMENDED" : score >= 60 ? "PROCEED_WITH_CAUTION" : "HIGH_RISK_AVOID");

  let verdictColorClass = "caution";
  let verdictText = "CẦN THẬN TRỌNG - XEM XÉT RỦI RO";
  let VerdictIcon = AlertTriangle;

  if (verdict === "STRONGLY_RECOMMENDED") {
    verdictColorClass = "recommended";
    verdictText = "KHUYẾN NGHỊ MẠNH MẼ - AN TOÀN ĐẦU TƯ";
    VerdictIcon = CheckCircle2;
  } else if (verdict === "HIGH_RISK_AVOID") {
    verdictColorClass = "avoid";
    verdictText = "RỦI RO CAO - CÂN NHẮC TRÁNH ĐẦU TƯ";
    VerdictIcon = ShieldAlert;
  }

  const scoreStrokeColor =
    verdictColorClass === "recommended" ? "#16a34a" : verdictColorClass === "caution" ? "#d97706" : "#dc2626";

  return (
    <div className="dd-modal-overlay" onClick={onClose}>
      <div className="dd-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="dd-modal-header">
          <div className="dd-header-left">
            <div className="dd-header-icon-box">
              <Scale size={24} />
            </div>
            <div className="dd-header-titles">
              <h3 className="dd-header-title">{property.title}</h3>
              <div className="dd-header-subtitle">
                <span className="dd-property-tag">
                  <MapPin size={11} />
                  {property.ward ? `${property.ward}, ` : ""}{property.district}
                </span>
                {areaM2 > 0 && (
                  <span className="dd-property-tag">
                    <Maximize2 size={11} />
                    {areaM2} m²
                  </span>
                )}
                <span className="dd-property-price-tag">{formatVND(propertyPrice)}</span>
                {userWallet?.balance !== undefined && (
                  <span className="dd-property-tag" title="Số dư ví AI">
                    <Wallet size={11} /> {formatVND(userWallet.balance)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <button className="dd-btn-close" onClick={onClose} title="Đóng">
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="dd-modal-body">
          {/* Error / Quota Notice */}
          {errorMessage && (
            <div className="dd-error-banner">
              <div className="dd-error-content">
                <AlertCircle size={18} />
                <span>{errorMessage}</span>
              </div>
              {isQuotaError && (
                <button className="dd-btn-topup" onClick={handleOpenTopupModal}>
                  Nạp tiền ngay
                </button>
              )}
            </div>
          )}

          {/* Quick Configuration Panel */}
          <div className={`dd-config-panel ${isConfigCollapsed ? "collapsed" : ""}`}>
            <div className="dd-config-header">
              <div className="dd-config-title">
                <Compass size={16} />
                <span>Thiết lập Mục tiêu & Phương án Vốn</span>
                {taskId && (
                  <span style={{ fontSize: "11px", color: "#94a3b8", fontWeight: 400 }}>
                    (Mã: {taskId})
                  </span>
                )}
              </div>
              {dossier && (
                <button
                  type="button"
                  className="dd-btn-toggle-config"
                  onClick={() => setIsConfigCollapsed(!isConfigCollapsed)}
                >
                  {isConfigCollapsed ? (
                    <>
                      <span>Xem lại cấu hình</span> <ChevronDown size={14} />
                    </>
                  ) : (
                    <>
                      <span>Thu gọn cấu hình</span> <ChevronUp size={14} />
                    </>
                  )}
                </button>
              )}
            </div>

            {!isConfigCollapsed && (
              <div className="dd-config-body">
                {/* Objective Selector */}
                <div className="dd-objectives-grid">
                  <button
                    type="button"
                    className={`dd-objective-card ${objective === "residential" ? "selected" : ""}`}
                    onClick={() => setObjective("residential")}
                    disabled={isAnalyzing}
                  >
                    <div className="dd-objective-label">
                      <Home size={16} />
                      <span>An cư lạc nghiệp</span>
                    </div>
                    <div className="dd-objective-desc">
                      Ưu tiên an toàn pháp lý tuyệt đối, hạ tầng sống và không ngập lụt.
                    </div>
                  </button>

                  <button
                    type="button"
                    className={`dd-objective-card ${objective === "rental_cashflow" ? "selected" : ""}`}
                    onClick={() => setObjective("rental_cashflow")}
                    disabled={isAnalyzing}
                  >
                    <div className="dd-objective-label">
                      <DollarSign size={16} />
                      <span>Dòng tiền cho thuê</span>
                    </div>
                    <div className="dd-objective-desc">
                      Tối ưu tỷ suất sinh lời cho thuê (Cap Rate) và khả năng trả nợ DSCR.
                    </div>
                  </button>

                  <button
                    type="button"
                    className={`dd-objective-card ${objective === "capital_gain" ? "selected" : ""}`}
                    onClick={() => setObjective("capital_gain")}
                    disabled={isAnalyzing}
                  >
                    <div className="dd-objective-label">
                      <TrendingUp size={16} />
                      <span>Lãi vốn 3-5 năm</span>
                    </div>
                    <div className="dd-objective-desc">
                      Kỳ vọng tăng giá theo quy hoạch hạ tầng giao thông và đô thị mới.
                    </div>
                  </button>
                </div>

                {/* Equity Ratio Slider & Live Loan Preview */}
                <div className="dd-simulator-row">
                  <div className="dd-slider-wrapper">
                    <div className="dd-slider-label-row">
                      <span>Tỷ lệ vốn tự có:</span>
                      <b>{Math.round(equityRatio * 100)}% ({formatShortVND(equityCapital)})</b>
                    </div>
                    <input
                      type="range"
                      min="0.3"
                      max="1.0"
                      step="0.05"
                      value={equityRatio}
                      disabled={isAnalyzing}
                      onChange={(e) => setEquityRatio(parseFloat(e.target.value))}
                      className="dd-equity-slider"
                    />
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#94a3b8" }}>
                      <span>30% (Đòn bẩy cao)</span>
                      <span>70% (Chuẩn)</span>
                      <span>100% (Tiền mặt)</span>
                    </div>
                  </div>

                  <div className="dd-loan-summary-box">
                    <div className="dd-loan-item">
                      <span>Vốn vay ngân hàng:</span>
                      <b>{formatShortVND(loanAmount)}</b>
                    </div>
                    <div className="dd-loan-item">
                      <span>Gốc + Lãi tháng đầu (ước tính):</span>
                      <b style={{ color: "#2563eb" }}>{formatVND(estimatedMonth1Payment)}/tháng</b>
                    </div>
                    <div className="dd-loan-item" style={{ fontSize: "11px", color: "#94a3b8" }}>
                      <span>Lãi suất tham chiếu:</span>
                      <span>8.5%/năm • 20 năm</span>
                    </div>
                  </div>
                </div>

                {/* Action Start Button */}
                {!dossier && (
                  <button
                    type="button"
                    className="dd-btn-start"
                    onClick={handleStartAnalysis}
                    disabled={isAnalyzing}
                  >
                    {isAnalyzing ? (
                      <>
                        <Loader2 size={18} className="spin-icon" />
                        <span>Đang thực hiện thẩm định AI...</span>
                      </>
                    ) : (
                      <>
                        <ShieldCheck size={18} />
                        <span>Bắt đầu Thẩm định Chuyên sâu</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Real-time 4-Stage Stepper */}
          {(isAnalyzing || dossier || currentStage !== "idle") && (
            <div className="dd-stepper-box">
              <div className="dd-stepper-header">
                <div className="dd-stepper-title">
                  <RotateCw size={15} className={isAnalyzing ? "spin-icon" : ""} />
                  <span>Tiến trình Thẩm định Đa tác nhân (Multi-Agent Engine)</span>
                </div>
                <div className="dd-stepper-percent">{progress}%</div>
              </div>

              <div className="dd-stepper-track-bar">
                <div className="dd-stepper-progress-fill" style={{ width: `${progress}%` }} />
              </div>

              <div className="dd-stepper-grid">
                {/* Step 1: Planning */}
                <div className={`dd-step-item ${getStepStatus(0)}`}>
                  <div className="dd-step-circle">
                    {getStepStatus(0) === "completed" ? (
                      <CheckCircle2 size={18} />
                    ) : getStepStatus(0) === "active" ? (
                      <Loader2 size={18} className="spin-icon" />
                    ) : (
                      "1"
                    )}
                  </div>
                  <div className="dd-step-title">Lập kế hoạch</div>
                  <div className="dd-step-subtitle">Phân rã mục tiêu (15%)</div>
                </div>

                {/* Step 2: Investigating */}
                <div className={`dd-step-item ${getStepStatus(1)}`}>
                  <div className="dd-step-circle">
                    {getStepStatus(1) === "completed" ? (
                      <CheckCircle2 size={18} />
                    ) : getStepStatus(1) === "active" ? (
                      <Loader2 size={18} className="spin-icon" />
                    ) : (
                      "2"
                    )}
                  </div>
                  <div className="dd-step-title">Điều tra đa nguồn</div>
                  <div className="dd-step-subtitle">Pháp lý, Giá, Ngập, Vốn (50%)</div>
                </div>

                {/* Step 3: Critiquing */}
                <div className={`dd-step-item ${getStepStatus(2)}`}>
                  <div className="dd-step-circle">
                    {getStepStatus(2) === "completed" ? (
                      <CheckCircle2 size={18} />
                    ) : getStepStatus(2) === "active" ? (
                      <Loader2 size={18} className="spin-icon" />
                    ) : (
                      "3"
                    )}
                  </div>
                  <div className="dd-step-title">Phản biện đối nghịch</div>
                  <div className="dd-step-subtitle">Devil's Advocate (75%)</div>
                </div>

                {/* Step 4: Synthesizing */}
                <div className={`dd-step-item ${getStepStatus(3)}`}>
                  <div className="dd-step-circle">
                    {getStepStatus(3) === "completed" ? (
                      <CheckCircle2 size={18} />
                    ) : getStepStatus(3) === "active" ? (
                      <Loader2 size={18} className="spin-icon" />
                    ) : (
                      "4"
                    )}
                  </div>
                  <div className="dd-step-title">Tổng hợp Dossier</div>
                  <div className="dd-step-subtitle">Chấm điểm & Báo cáo (100%)</div>
                </div>
              </div>

              {stageDescription && (
                <div className="dd-stage-msg-box">
                  <AlertCircle size={14} />
                  <span>{stageDescription}</span>
                </div>
              )}
            </div>
          )}

          {/* Dossier Viewer (when completed and dossier available) */}
          {dossier && (
            <>
              {/* Scorecard Gauge & Verdict Banner */}
              <div className="dd-scorecard-card">
                <div className="dd-score-gauge-box">
                  <svg className="dd-score-svg" viewBox="0 0 120 120">
                    <circle
                      cx="60"
                      cy="60"
                      r={radius}
                      fill="none"
                      stroke="#f1f5f9"
                      strokeWidth="10"
                    />
                    <circle
                      cx="60"
                      cy="60"
                      r={radius}
                      fill="none"
                      stroke={scoreStrokeColor}
                      strokeWidth="10"
                      strokeDasharray={circumference}
                      strokeDashoffset={strokeDashoffset}
                      strokeLinecap="round"
                      style={{ transition: "stroke-dashoffset 0.8s ease" }}
                    />
                  </svg>
                  <div className="dd-score-inner-text">
                    <span className="dd-score-number">{score}</span>
                    <span className="dd-score-max">/ 100</span>
                  </div>
                </div>

                <div className="dd-scorecard-details">
                  <div className={`dd-verdict-pill ${verdictColorClass}`}>
                    <VerdictIcon size={14} />
                    <span>{verdictText}</span>
                  </div>

                  <div className="dd-exec-summary-box">
                    {dossier.executive_summary}
                  </div>

                  {/* 4 Pillar Mini Progress Bars */}
                  <div className="dd-pillars-grid">
                    <div className="dd-pillar-item">
                      <div className="dd-pillar-label-row">
                        <span>Pháp lý (35%)</span>
                        <b>{dossier.legal?.legal_safety_score ?? 0}đ</b>
                      </div>
                      <div className="dd-pillar-bar-track">
                        <div
                          className="dd-pillar-bar-fill"
                          style={{
                            width: `${dossier.legal?.legal_safety_score ?? 0}%`,
                            background: "#2563eb"
                          }}
                        />
                      </div>
                    </div>

                    <div className="dd-pillar-item">
                      <div className="dd-pillar-label-row">
                        <span>Định giá (25%)</span>
                        <b>
                          {dossier.valuation?.valuation_status === "under_priced"
                            ? "Tốt"
                            : dossier.valuation?.valuation_status === "fair"
                            ? "Hợp lý"
                            : "Cao"}
                        </b>
                      </div>
                      <div className="dd-pillar-bar-track">
                        <div
                          className="dd-pillar-bar-fill"
                          style={{
                            width:
                              dossier.valuation?.valuation_status === "under_priced"
                                ? "90%"
                                : dossier.valuation?.valuation_status === "fair"
                                ? "75%"
                                : "50%",
                            background: "#10b981"
                          }}
                        />
                      </div>
                    </div>

                    <div className="dd-pillar-item">
                      <div className="dd-pillar-label-row">
                        <span>Hạ tầng (20%)</span>
                        <b>{dossier.climate_infrastructure?.infrastructure_score ?? 0}đ</b>
                      </div>
                      <div className="dd-pillar-bar-track">
                        <div
                          className="dd-pillar-bar-fill"
                          style={{
                            width: `${dossier.climate_infrastructure?.infrastructure_score ?? 0}%`,
                            background: "#06b6d4"
                          }}
                        />
                      </div>
                    </div>

                    <div className="dd-pillar-item">
                      <div className="dd-pillar-label-row">
                        <span>Tài chính (20%)</span>
                        <b>{dossier.financial?.stress_test_passed ? "Đạt" : "Cảnh báo"}</b>
                      </div>
                      <div className="dd-pillar-bar-track">
                        <div
                          className="dd-pillar-bar-fill"
                          style={{
                            width: dossier.financial?.stress_test_passed ? "85%" : "45%",
                            background: dossier.financial?.stress_test_passed ? "#16a34a" : "#dc2626"
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 7 Tab Navigation Bar */}
              <div className="dd-tabs-bar">
                <button
                  type="button"
                  className={`dd-tab-btn ${activeTab === "overview" ? "active" : ""}`}
                  onClick={() => setActiveTab("overview")}
                >
                  <Layers size={14} />
                  <span>Tổng quan</span>
                </button>

                <button
                  type="button"
                  className={`dd-tab-btn ${activeTab === "legal" ? "active" : ""}`}
                  onClick={() => setActiveTab("legal")}
                >
                  <Scale size={14} />
                  <span>Pháp lý & Quy hoạch</span>
                </button>

                <button
                  type="button"
                  className={`dd-tab-btn ${activeTab === "valuation" ? "active" : ""}`}
                  onClick={() => setActiveTab("valuation")}
                >
                  <TrendingUp size={14} />
                  <span>Định giá thị trường</span>
                </button>

                <button
                  type="button"
                  className={`dd-tab-btn ${activeTab === "climate" ? "active" : ""}`}
                  onClick={() => setActiveTab("climate")}
                >
                  <CloudRain size={14} />
                  <span>Hạ tầng & Ngập lụt</span>
                </button>

                <button
                  type="button"
                  className={`dd-tab-btn ${activeTab === "financial" ? "active" : ""}`}
                  onClick={() => setActiveTab("financial")}
                >
                  <Calculator size={14} />
                  <span>Mô phỏng tài chính</span>
                </button>

                <button
                  type="button"
                  className={`dd-tab-btn ${activeTab === "critic" ? "active" : ""}`}
                  onClick={() => setActiveTab("critic")}
                >
                  <Flame size={14} />
                  <span>Phản biện rủi ro</span>
                </button>

                <button
                  type="button"
                  className={`dd-tab-btn ${activeTab === "markdown" ? "active" : ""}`}
                  onClick={() => setActiveTab("markdown")}
                >
                  <BookOpen size={14} />
                  <span>Đàm phán & Báo cáo</span>
                </button>
              </div>

              {/* Tab 1: Overview */}
              {activeTab === "overview" && (
                <div className="dd-tab-pane">
                  <div className="dd-metrics-grid">
                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <ShieldCheck size={14} /> Điểm an toàn pháp lý
                      </div>
                      <div className="dd-metric-val">{dossier.legal?.legal_safety_score ?? 0} / 100</div>
                      <div className="dd-metric-sub">{dossier.legal?.title_deed_status || "Sổ hồng"}</div>
                    </div>

                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <TrendingUp size={14} /> Đơn giá / m²
                      </div>
                      <div className="dd-metric-val">{formatShortVND(dossier.valuation?.unit_price_per_m2)}/m²</div>
                      <div className="dd-metric-sub">
                        Trung bình quận: {formatShortVND(dossier.valuation?.avg_district_price_per_m2)}/m²
                      </div>
                    </div>

                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <Droplets size={14} /> Rủi ro ngập lụt
                      </div>
                      <div className="dd-metric-val" style={{ textTransform: "capitalize" }}>
                        {dossier.climate_infrastructure?.flood_risk_level === "low"
                          ? "Thấp (An toàn)"
                          : dossier.climate_infrastructure?.flood_risk_level === "medium"
                          ? "Trung bình"
                          : "Cao (Cảnh báo)"}
                      </div>
                      <div className="dd-metric-sub">
                        Hạ tầng: {dossier.climate_infrastructure?.infrastructure_score ?? 0}đ
                      </div>
                    </div>

                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <DollarSign size={14} /> Khả năng trả nợ DSCR
                      </div>
                      <div className="dd-metric-val">{dossier.financial?.dscr_ratio ?? 0}x</div>
                      <div className="dd-metric-sub">
                        {dossier.financial?.stress_test_passed ? "Vượt qua Stress test +3%" : "Chưa đạt Stress test"}
                      </div>
                    </div>
                  </div>

                  <div className="dd-info-card">
                    <div className="dd-info-card-header">
                      <Award size={15} />
                      <span>Kết luận Phân tích Điều tra Tổng hợp</span>
                    </div>
                    <div className="dd-info-card-body">
                      {dossier.executive_summary}
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 2: Legal Risk & Citations */}
              {activeTab === "legal" && (
                <div className="dd-tab-pane">
                  <div className="dd-legal-status-grid">
                    <div className="dd-info-card">
                      <div className="dd-info-card-header">
                        <ShieldCheck size={16} />
                        <span>Tình trạng Sổ hồng & Giấy tờ</span>
                      </div>
                      <div className="dd-info-card-body">
                        {dossier.legal?.title_deed_status || "Chưa xác minh"}
                      </div>
                    </div>

                    <div className="dd-info-card">
                      <div className="dd-info-card-header">
                        <Building2 size={16} />
                        <span>Quy hoạch Đô thị & Phân khu</span>
                      </div>
                      <div className="dd-info-card-body">
                        {dossier.legal?.zoning_status || "Đang kiểm tra quy hoạch"}
                      </div>
                    </div>
                  </div>

                  {dossier.legal?.risks_detected && dossier.legal.risks_detected.length > 0 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      <div style={{ fontSize: "13px", fontWeight: 700, color: "#991b1b", display: "flex", alignItems: "center", gap: "6px" }}>
                        <ShieldAlert size={15} />
                        <span>Các cảnh báo và rủi ro pháp lý phát hiện ({dossier.legal.risks_detected.length}):</span>
                      </div>
                      <div className="dd-risks-list">
                        {dossier.legal.risks_detected.map((risk, idx) => (
                          <div key={idx} className="dd-risk-item">
                            <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: "2px" }} />
                            <span>{risk}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {dossier.legal?.citations && dossier.legal.citations.length > 0 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      <div style={{ fontSize: "13px", fontWeight: 700, color: "#1e293b", display: "flex", alignItems: "center", gap: "6px" }}>
                        <Scale size={15} />
                        <span>Căn cứ pháp luật Việt Nam trích dẫn (Luật Đất đai 2024 & Luật Nhà ở 2023):</span>
                      </div>
                      <div className="dd-citations-list">
                        {dossier.legal.citations.map((cite, idx) => (
                          <div key={idx} className="dd-citation-card">
                            <div className="dd-citation-header">
                              <BookOpen size={14} />
                              <span>{cite.doc_title || "Văn bản Luật"} - {cite.article || "Điều khoản"}</span>
                            </div>
                            <div className="dd-citation-quote">
                              "{cite.content || "Nội dung điều khoản đang được rà soát."}"
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 3: Market Valuation */}
              {activeTab === "valuation" && (
                <div className="dd-tab-pane">
                  <div className="dd-valuation-benchmark-row">
                    <div>
                      <div style={{ fontSize: "12px", color: "#64748b", marginBottom: "4px" }}>Đơn giá BĐS thẩm định:</div>
                      <div style={{ fontSize: "20px", fontWeight: 800, color: "#0f172a" }}>
                        {formatVND(dossier.valuation?.unit_price_per_m2)} / m²
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: "12px", color: "#64748b", marginBottom: "4px" }}>Mặt bằng trung bình khu vực quận:</div>
                      <div style={{ fontSize: "20px", fontWeight: 800, color: "#2563eb" }}>
                        {formatVND(dossier.valuation?.avg_district_price_per_m2)} / m²
                      </div>
                    </div>

                    <div style={{ gridColumn: "1 / -1", display: "flex", alignItems: "center", gap: "10px" }}>
                      <span style={{ fontSize: "12.5px", fontWeight: 600, color: "#475569" }}>Trạng thái định giá:</span>
                      <span className={`dd-val-status-chip ${dossier.valuation?.valuation_status || "fair"}`}>
                        {dossier.valuation?.valuation_status === "under_priced"
                          ? "✓ Định giá thấp hơn mặt bằng (Cơ hội tốt)"
                          : dossier.valuation?.valuation_status === "fair"
                          ? "≈ Mức giá sát thị trường (Hợp lý)"
                          : "⚠ Định giá cao hơn mặt bằng quận"}
                      </span>
                    </div>
                  </div>

                  {dossier.valuation?.comparable_properties && dossier.valuation.comparable_properties.length > 0 && (
                    <div>
                      <div style={{ fontSize: "13px", fontWeight: 700, color: "#1e293b", marginBottom: "10px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <Search size={15} />
                        <span>Bất động sản tương đồng cùng phân khúc để đối chứng ({dossier.valuation.comparable_properties.length}):</span>
                      </div>
                      <div className="dd-table-container">
                        <table className="dd-data-table">
                          <thead>
                            <tr>
                              <th>Tên / Tiêu đề BĐS</th>
                              <th>Diện tích</th>
                              <th>Tổng giá VNĐ</th>
                              <th>Đơn giá / m²</th>
                            </tr>
                          </thead>
                          <tbody>
                            {dossier.valuation.comparable_properties.map((comp, idx) => (
                              <tr key={idx}>
                                <td style={{ fontWeight: 600 }}>{comp.title}</td>
                                <td>{comp.area} m²</td>
                                <td>{formatVND(comp.price)}</td>
                                <td style={{ color: "#2563eb", fontWeight: 700 }}>
                                  {formatShortVND(comp.unit_price_per_m2)}/m²
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 4: Climate & Flood Infrastructure */}
              {activeTab === "climate" && (
                <div className="dd-tab-pane">
                  <div className={`dd-flood-status-box ${dossier.climate_infrastructure?.flood_risk_level || "low"}`}>
                    <CloudRain size={24} style={{ flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: "14px", fontWeight: 800 }}>
                        Mức độ nguy cơ ngập lụt:{" "}
                        {dossier.climate_infrastructure?.flood_risk_level === "low"
                          ? "Thấp - Khu vực cao ráo, thoát nước tốt"
                          : dossier.climate_infrastructure?.flood_risk_level === "medium"
                          ? "Trung bình - Có thể ngập cục bộ khi triều cường hoặc mưa cực đoan"
                          : "Cao - Cảnh báo vùng trũng thấp hoặc ven sông"}
                      </div>
                      <div style={{ fontSize: "12.5px", marginTop: "4px", opacity: 0.9 }}>
                        Điểm hạ tầng đô thị: <b>{dossier.climate_infrastructure?.infrastructure_score ?? 0} / 100</b>
                      </div>
                    </div>
                  </div>

                  <div className="dd-info-card">
                    <div className="dd-info-card-header">
                      <Droplets size={15} />
                      <span>Phân tích Thủy văn & Lịch sử ngập lụt Đà Nẵng</span>
                    </div>
                    <div className="dd-info-card-body">
                      {dossier.climate_infrastructure?.flood_notes || "Khu vực không ghi nhận điểm ngập nghiêm trọng trong các đợt mưa lũ lịch sử."}
                    </div>
                  </div>

                  {dossier.climate_infrastructure?.key_amenities && dossier.climate_infrastructure.key_amenities.length > 0 && (
                    <div>
                      <div style={{ fontSize: "13px", fontWeight: 700, color: "#1e293b", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <Building2 size={15} />
                        <span>Tiện ích và hạ tầng kết nối trọng điểm:</span>
                      </div>
                      <div className="dd-amenities-wrap">
                        {dossier.climate_infrastructure.key_amenities.map((amenity, idx) => (
                          <div key={idx} className="dd-amenity-chip">
                            <MapPin size={12} color="#2563eb" />
                            <span>{amenity}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 5: Financial Feasibility */}
              {activeTab === "financial" && (
                <div className="dd-tab-pane">
                  <div className="dd-financial-grid">
                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <DollarSign size={14} /> Khoản vay ngân hàng
                      </div>
                      <div className="dd-metric-val">{formatShortVND(dossier.financial?.loan_amount_vnd ?? loanAmount)}</div>
                      <div className="dd-metric-sub">Vốn tự có: {formatShortVND(equityCapital)}</div>
                    </div>

                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <Calculator size={14} /> Trả góp tháng đầu
                      </div>
                      <div className="dd-metric-val" style={{ color: "#2563eb" }}>
                        {formatVND(dossier.financial?.monthly_repayment_vnd)}
                      </div>
                      <div className="dd-metric-sub">Dư nợ giảm dần</div>
                    </div>

                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <Percent size={14} /> Lãi suất hiệu dụng
                      </div>
                      <div className="dd-metric-val">{dossier.financial?.effective_interest_rate ?? 8.5}% / năm</div>
                      <div className="dd-metric-sub">Ưu đãi cố định 12-24 tháng</div>
                    </div>

                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <Home size={14} /> Doanh thu cho thuê ước tính
                      </div>
                      <div className="dd-metric-val">
                        {formatVND(dossier.financial?.estimated_monthly_rental_income)} / tháng
                      </div>
                      <div className="dd-metric-sub">Khảo sát giá thuê thực tế</div>
                    </div>

                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <TrendingUp size={14} /> Tỷ suất cho thuê ròng
                      </div>
                      <div className="dd-metric-val">{dossier.financial?.net_rental_yield_percent ?? 0}% / năm</div>
                      <div className="dd-metric-sub">Net Rental Yield</div>
                    </div>

                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <ShieldCheck size={14} /> Hệ số bao nợ DSCR
                      </div>
                      <div className="dd-metric-val">{dossier.financial?.dscr_ratio ?? 0}x</div>
                      <div className="dd-metric-sub">&gt; 1.25x là an toàn dòng tiền</div>
                    </div>
                  </div>

                  <div className={`dd-stress-test-card ${dossier.financial?.stress_test_passed ? "passed" : "failed"}`}>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      {dossier.financial?.stress_test_passed ? <CheckCircle2 size={24} /> : <AlertTriangle size={24} />}
                      <div>
                        <div style={{ fontSize: "14px", fontWeight: 800 }}>
                          {dossier.financial?.stress_test_passed
                            ? "ĐẠT - Vượt qua kịch bản kiểm tra sức chịu tải (Stress Test)"
                            : "CẢNH BÁO - Nguy cơ rủi ro dòng tiền khi lãi suất tăng"}
                        </div>
                        <div style={{ fontSize: "12px", marginTop: "2px" }}>
                          Mô phỏng kịch bản lãi suất thả nổi tăng thêm +3.0% sau thời gian ưu đãi.
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 6: Adversarial Risk Critic */}
              {activeTab === "critic" && (
                <div className="dd-tab-pane">
                  <div style={{ fontSize: "13px", color: "#64748b", lineHeight: 1.45 }}>
                    Góc nhìn độc lập <b>Devil's Advocate Critic</b>: Đóng vai trò chuyên gia phản biện đối lập để bóc tách những rủi ro ngầm, góc khuất và các giả định quá lạc quan của nhà đầu tư.
                  </div>

                  <div className="dd-critic-list">
                    {dossier.critic_counterarguments && dossier.critic_counterarguments.length > 0 ? (
                      dossier.critic_counterarguments.map((arg, idx) => (
                        <div key={idx} className="dd-critic-item">
                          <Flame size={18} style={{ flexShrink: 0, marginTop: "2px", color: "#d97706" }} />
                          <span>{arg}</span>
                        </div>
                      ))
                    ) : (
                      <div style={{ fontSize: "13px", color: "#64748b" }}>
                        Chưa ghi nhận luận điểm phản biện đặc biệt nào.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 7: Actionable Levers & Full Markdown Report */}
              {activeTab === "markdown" && (
                <div className="dd-tab-pane">
                  {dossier.actionable_negotiation_points && dossier.actionable_negotiation_points.length > 0 && (
                    <div>
                      <div style={{ fontSize: "13.5px", fontWeight: 700, color: "#14532d", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <Handshake size={16} />
                        <span>Đòn bẩy đàm phán hành động (Negotiation Levers):</span>
                      </div>
                      <div className="dd-negotiation-list">
                        {dossier.actionable_negotiation_points.map((pt, idx) => (
                          <div key={idx} className="dd-negotiation-item">
                            <Check size={16} style={{ flexShrink: 0, marginTop: "2px", color: "#16a34a" }} />
                            <span>{pt}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div style={{ marginTop: "10px" }}>
                    <div className="dd-markdown-toolbar">
                      <span style={{ fontSize: "13.5px", fontWeight: 700, color: "#0f172a", display: "flex", alignItems: "center", gap: "6px" }}>
                        <BookOpen size={16} />
                        <span>Báo cáo Thẩm định Dossier Toàn diện</span>
                      </span>

                      <button
                        type="button"
                        className={`dd-btn-copy-markdown ${copiedMarkdown ? "copied" : ""}`}
                        onClick={handleCopyMarkdown}
                      >
                        {copiedMarkdown ? (
                          <>
                            <Check size={14} />
                            <span>Đã sao chép!</span>
                          </>
                        ) : (
                          <>
                            <Copy size={14} />
                            <span>Sao chép Markdown</span>
                          </>
                        )}
                      </button>
                    </div>

                    <div className="dd-markdown-rendered-view">
                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                        {dossier.full_markdown_report || "Báo cáo đang được tổng hợp..."}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
