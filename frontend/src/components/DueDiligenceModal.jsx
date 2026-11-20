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
  Wallet,
  Globe,
  ExternalLink,
  Download,
  FileText,
  Printer,
  Zap
} from "lucide-react";
import "./DueDiligenceModal.css";

const getFriendlyVerdict = (verdict) => {
  switch (verdict) {
    case "STRONGLY_RECOMMENDED":
      return "Khuyến nghị mạnh mẽ (An toàn đầu tư)";
    case "PROCEED_WITH_CAUTION":
      return "Cần thận trọng (Xem xét rủi ro & Đàm phán thêm)";
    case "HIGH_RISK_AVOID":
      return "Rủi ro cao (Cân nhắc tránh đầu tư)";
    default:
      return verdict || "Đang đánh giá";
  }
};

const formatFriendlyText = (text) => {
  if (!text || typeof text !== "string") return text || "";
  return text
    .replace(/`?STRONGLY_RECOMMENDED`?/g, "Khuyến nghị mạnh mẽ (An toàn đầu tư)")
    .replace(/`?PROCEED_WITH_CAUTION`?/g, "Cần thận trọng (Xem xét rủi ro & Đàm phán thêm)")
    .replace(/`?HIGH_RISK_AVOID`?/g, "Rủi ro cao (Cân nhắc tránh đầu tư)")
    .replace(/`?under_priced`?/g, "Giá tốt hơn thị trường (Rẻ hơn mặt bằng chung)")
    .replace(/`?over_priced`?/g, "Giá cao hơn thị trường (Cần đàm phán giảm giá)")
    .replace(/`?fair`?/g, "Mức giá hợp lý (Sát mặt bằng chung)")
    .replace(/`?residential`?/g, "Mua để ở (An cư)")
    .replace(/`?rental_cashflow`?/g, "Khai thác dòng tiền cho thuê")
    .replace(/`?capital_gain`?/g, "Đầu tư lãi vốn tăng giá")
    .replace(/`?low`?/g, "Thấp (An toàn ngập lụt)")
    .replace(/`?medium`?/g, "Trung bình (Ngập úng tạm thời khi triều cường)")
    .replace(/`?high`?/g, "Cao (Khu vực trũng thấp ven sông, dễ ngập mùa mưa)");
};

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

const formatMillionPerM2 = (val) => {
  if (val === undefined || val === null || isNaN(val)) return "0.0 triệu/m²";
  return `${(Number(val) / 1_000_000).toFixed(1)} triệu/m²`;
};

const formatMillionPrice = (val, unit = "triệu đ") => {
  if (val === undefined || val === null || isNaN(val)) return `0.0 ${unit}`;
  const numInMillion = Number(val) / 1_000_000;
  return `${numInMillion.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} ${unit}`;
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
  onWalletUpdate,
  initialDossier = null,
  initialTaskId = null,
  initialIsCached = false
}) {
  const [objective, setObjective] = useState("residential");
  const [equityRatio, setEquityRatio] = useState(0.7);
  const [isConfigCollapsed, setIsConfigCollapsed] = useState(false);
  const [enableDeepResearch, setEnableDeepResearch] = useState(false);
  const [developerName, setDeveloperName] = useState("");

  // Execution & Stream State
  const [taskId, setTaskId] = useState(null);
  const [isCached, setIsCached] = useState(false);
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

    if (!isOpen || (isNewProp && !initialDossier)) {
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
      setIsCached(false);
      setIsAnalyzing(false);
      setCurrentStage("idle");
      setProgress(0);
      setStageDescription("");
      setErrorMessage(null);
      setIsQuotaError(false);
      setIsConfigCollapsed(false);
      setActiveTab("overview");
    }

    if (isOpen && initialDossier) {
      setDossier(initialDossier);
      if (initialTaskId) setTaskId(initialTaskId);
      setIsCached(Boolean(initialIsCached));
      setIsAnalyzing(false);
      setCurrentStage("completed");
      setProgress(100);
      setIsConfigCollapsed(true);
      setActiveTab("overview");
    }
  }, [isOpen, property?.id, initialDossier, initialTaskId, initialIsCached]);

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
          user_id: userId,
          enable_deep_research: enableDeepResearch,
          developer_name: developerName.trim() || undefined
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
      if (data.is_cached) {
        setIsCached(true);
      }

      // Trigger wallet refresh if caller provided a callback
      if (onWalletUpdate && userId) {
        fetch(`${API_BASE}/api/user/wallet?user_id=${encodeURIComponent(userId)}`)
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
          if (payload.is_cached) setIsCached(true);
          const finalDossier = payload.dossier || payload.result;
          if (finalDossier) setDossier(finalDossier);

          // Update user wallet balance if callback provided
          if (onWalletUpdate && userId) {
            fetch(`${API_BASE}/api/user/wallet?user_id=${encodeURIComponent(userId)}`)
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
            fetch(`${API_BASE}/api/user/wallet?user_id=${encodeURIComponent(userId)}`)
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
  let verdictText = "Cần thận trọng (Xem xét rủi ro & Đàm phán thêm)";
  let VerdictIcon = AlertTriangle;

  if (verdict === "STRONGLY_RECOMMENDED") {
    verdictColorClass = "recommended";
    verdictText = "Khuyến nghị mạnh mẽ (An toàn đầu tư)";
    VerdictIcon = CheckCircle2;
  } else if (verdict === "HIGH_RISK_AVOID") {
    verdictColorClass = "avoid";
    verdictText = "Rủi ro cao (Cân nhắc tránh đầu tư)";
    VerdictIcon = ShieldAlert;
  }

  if (dossier?.verdict_label) {
    verdictText = dossier.verdict_label;
  }

  const scoreStrokeColor =
    verdictColorClass === "recommended" ? "#16a34a" : verdictColorClass === "caution" ? "#d97706" : "#dc2626";

  const generatePrintableHtml = () => {
    if (!dossier) return "";
    const title = property?.title || "Bất động sản Đà Nẵng";
    const district = property?.district || property?.location || "Đà Nẵng";
    const ward = property?.ward || "";
    const area = areaM2 || 0;
    const price = propertyPrice || 0;
    const unitPrice = area > 0 ? Math.round(price / area) : 0;
    const dateStr = new Date().toLocaleDateString("vi-VN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });

    const friendlyVerdict = dossier.verdict_label || getFriendlyVerdict(dossier.verdict || verdict);
    const friendlyExec = formatFriendlyText(dossier.executive_summary || "");
    const friendlyMarkdown = formatFriendlyText(dossier.full_markdown_report || "");

    const formattedReport = friendlyMarkdown
      .split("\n")
      .map((line) => {
        const trimmed = line.trim();
        if (!trimmed) return "<div style='height:6px;'></div>";
        if (trimmed.startsWith("# ")) {
          return `<h1 style="color:#1e3a8a; font-size:16px; border-bottom:2px solid #2563eb; padding-bottom:5px; margin:14px 0 8px 0;">${trimmed.slice(2)}</h1>`;
        }
        if (trimmed.startsWith("## ")) {
          return `<h2 style="color:#0f172a; font-size:14px; border-bottom:1px solid #e2e8f0; padding-bottom:4px; margin:12px 0 6px 0;">${trimmed.slice(3)}</h2>`;
        }
        if (trimmed.startsWith("### ")) {
          return `<h3 style="color:#334155; font-size:12.5px; margin:8px 0 4px 0;">${trimmed.slice(4)}</h3>`;
        }
        if (trimmed.startsWith("- ")) {
          const content = trimmed.slice(2).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/\*(.*?)\*/g, "<em>$1</em>");
          return `<div style="display:flex; margin:3px 0; font-size:11.5px; line-height:1.5;"><span style="color:#2563eb; margin-right:6px;">•</span><span>${content}</span></div>`;
        }
        const text = trimmed.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/\*(.*?)\*/g, "<em>$1</em>");
        return `<p style="margin:3px 0; font-size:11.5px; line-height:1.5;">${text}</p>`;
      })
      .join("");

    return `<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>Bao_Cao_Tham_Dinh_${title.replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1E00-\u1EFF]/g, "_")}_${new Date().toISOString().slice(0, 10)}</title>
  <style>
    @page {
      size: A4;
      margin: 12mm 15mm;
    }
    * {
      box-sizing: border-box;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #0f172a;
      line-height: 1.45;
      font-size: 11.5px;
      margin: 0;
      padding: 0;
      background: #ffffff;
    }
    .print-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2.5px solid #1e3a8a;
      padding-bottom: 10px;
      margin-bottom: 12px;
    }
    .header-logo-title h1 {
      margin: 0;
      font-size: 15px;
      color: #1e3a8a;
      text-transform: uppercase;
      font-weight: 800;
      letter-spacing: 0.5px;
    }
    .header-logo-title p {
      margin: 2px 0 0 0;
      font-size: 10.5px;
      color: #64748b;
      font-weight: 600;
    }
    .header-meta {
      text-align: right;
      font-size: 10px;
      color: #475569;
    }
    .header-meta strong {
      color: #0f172a;
    }
    .summary-card {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 10px 14px;
      margin-bottom: 12px;
    }
    .prop-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 11px;
    }
    .prop-table td {
      padding: 4px 6px;
      border-bottom: 1px solid #e2e8f0;
    }
    .prop-table td:nth-child(odd) {
      color: #64748b;
      font-weight: 500;
      width: 22%;
    }
    .prop-table td:nth-child(even) {
      color: #0f172a;
      font-weight: 600;
      width: 28%;
    }
    .verdict-banner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 12px;
      background: ${verdictColorClass === "recommended" ? "#f0fdf4" : verdictColorClass === "caution" ? "#fffbeb" : "#fef2f2"};
      border: 1.5px solid ${verdictColorClass === "recommended" ? "#86efac" : verdictColorClass === "caution" ? "#fde68a" : "#fecaca"};
    }
    .score-badge {
      font-size: 24px;
      font-weight: 800;
      color: ${scoreStrokeColor};
      background: #ffffff;
      padding: 6px 14px;
      border-radius: 8px;
      border: 1.5px solid ${scoreStrokeColor};
      display: inline-block;
      margin-right: 12px;
    }
    .verdict-label {
      font-size: 14px;
      font-weight: 700;
      color: ${scoreStrokeColor};
    }
    .verdict-sub {
      font-size: 11px;
      color: #475569;
      margin-top: 3px;
      line-height: 1.4;
    }
    .pillars-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
      margin-bottom: 12px;
    }
    .pillar-box {
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 8px 10px;
      background: #ffffff;
      text-align: center;
    }
    .pillar-title {
      font-size: 10px;
      color: #64748b;
      text-transform: uppercase;
      font-weight: 600;
    }
    .pillar-score {
      font-size: 14px;
      font-weight: 700;
      color: #1e3a8a;
      margin-top: 2px;
    }
    .report-content {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 12px 16px;
      margin-top: 8px;
    }
    .footer-seal {
      margin-top: 20px;
      padding-top: 10px;
      border-top: 1px solid #cbd5e1;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      font-size: 9.5px;
      color: #64748b;
    }
    .seal-box {
      border: 1.5px dashed #2563eb;
      border-radius: 6px;
      padding: 5px 12px;
      text-align: center;
      color: #1e3a8a;
      font-weight: 700;
      background: #f0f7ff;
    }
  </style>
</head>
<body>
  <div class="print-header">
    <div class="header-logo-title">
      <h1>HỆ THỐNG THẨM ĐỊNH BẤT ĐỘNG SẢN ĐÀ NẴNG</h1>
      <p>BÁO CÁO THẨM ĐỊNH CHUYÊN SÂU (DEEP DUE DILIGENCE DOSSIER)</p>
    </div>
    <div class="header-meta">
      <div>Mã tác vụ: <strong>${taskId || "DD-REPORT"}</strong></div>
      <div>Thời gian xuất: <strong>${dateStr}</strong></div>
      <div>Trạng thái: <strong>ĐÃ HOÀN TẤT (100%)</strong></div>
    </div>
  </div>

  <div class="summary-card">
    <table class="prop-table">
      <tr>
        <td>Tên tài sản:</td>
        <td colspan="3"><strong style="font-size:12px; color:#1e3a8a;">${title}</strong></td>
      </tr>
      <tr>
        <td>Địa bàn:</td>
        <td>${ward ? `${ward}, ` : ""}${district}, TP. Đà Nẵng</td>
        <td>Quy mô diện tích:</td>
        <td><strong>${area} m²</strong></td>
      </tr>
      <tr>
        <td>Giá chào bán:</td>
        <td><strong style="color:#b91c1c;">${formatMillionPrice(price)}</strong></td>
        <td>Đơn giá tham chiếu:</td>
        <td>${formatMillionPerM2(unitPrice)}</td>
      </tr>
      <tr>
        <td>Mục tiêu đầu tư:</td>
        <td>${objective === "residential" ? "Mua để ở (An cư)" : objective === "rental_cashflow" ? "Dòng tiền cho thuê" : "Đầu tư lãi vốn"}</td>
        <td>Cơ cấu tài chính:</td>
        <td>Vốn tự có ${Math.round(equityRatio * 100)}% (${formatMillionPrice(equityCapital)}) - Vay ${formatMillionPrice(loanAmount)}</td>
      </tr>
    </table>
  </div>

  <div class="verdict-banner">
    <div style="display:flex; align-items:center; width:100%;">
      <div class="score-badge">${score} <span style="font-size:11px; font-weight:500; color:#64748b;">/ 100</span></div>
      <div style="flex:1;">
        <div class="verdict-label">${friendlyVerdict}</div>
        <div class="verdict-sub">${friendlyExec}</div>
      </div>
    </div>
  </div>

  <div class="pillars-grid">
    <div class="pillar-box">
      <div class="pillar-title">1. Pháp lý (35%)</div>
      <div class="pillar-score" style="color:#2563eb;">${dossier.legal?.legal_safety_score ?? 0}đ</div>
      <div style="font-size:9.5px; color:#64748b; margin-top:1px;">An toàn sổ hồng</div>
    </div>
    <div class="pillar-box">
      <div class="pillar-title">2. Định giá (25%)</div>
      <div class="pillar-score" style="color:#10b981;">
        ${dossier.valuation?.valuation_status === "under_priced" ? "Giá tốt" : dossier.valuation?.valuation_status === "fair" ? "Mức giá hợp lý" : "Giá cao"}
      </div>
      <div style="font-size:9.5px; color:#64748b; margin-top:1px;">So sánh mặt bằng</div>
    </div>
    <div class="pillar-box">
      <div class="pillar-title">3. Hạ tầng & Thủy văn (20%)</div>
      <div class="pillar-score" style="color:#06b6d4;">${dossier.climate_infrastructure?.infrastructure_score ?? 0}đ</div>
      <div style="font-size:9.5px; color:#64748b; margin-top:1px;">
        ${dossier.climate_infrastructure?.flood_risk_level === "low" ? "An toàn ngập" : dossier.climate_infrastructure?.flood_risk_level === "medium" ? "Ngập tạm thời" : "Vùng trũng lũ"}
      </div>
    </div>
    <div class="pillar-box">
      <div class="pillar-title">4. Tài chính (20%)</div>
      <div class="pillar-score" style="color:${dossier.financial?.stress_test_passed ? "#16a34a" : "#dc2626"};">
        ${dossier.financial?.stress_test_passed ? "Đạt Stress-test" : "Cảnh báo lãi suất"}
      </div>
      <div style="font-size:9.5px; color:#64748b; margin-top:1px;">DSCR ${dossier.financial?.dscr_ratio ?? 0}x</div>
    </div>
  </div>

  ${dossier.deep_research ? `
  <div style="background:#f0f9ff; border:1px solid #bae6fd; border-radius:6px; padding:7px 12px; margin-top:8px; font-size:10.5px;">
    <strong>🕵️ Deep Research Tín nhiệm Chủ đầu tư:</strong> ${dossier.deep_research.target_entity} — Điểm tín nhiệm: <strong>${dossier.deep_research.reputation_score}/100</strong> (${dossier.deep_research.community_sentiment?.toUpperCase()}).
  </div>
  ` : ""}

  <div style="font-size:13px; font-weight:700; color:#1e3a8a; border-bottom:1.5px solid #2563eb; padding-bottom:4px; margin:14px 0 8px 0;">
    Báo Cáo Thẩm Định Chi Tiết
  </div>
  <div class="report-content">
    ${formattedReport}
  </div>

  <div class="footer-seal">
    <div>
      <div>Báo cáo được khởi tạo tự động bởi AI Engine Thẩm Định BĐS Đà Nẵng.</div>
      <div>Trích xuất và đối soát dữ liệu quy hoạch địa chính và thị trường thực tế.</div>
    </div>
    <div class="seal-box">
      <div>✓ ĐÃ XÁC THỰC HỆ THỐNG</div>
      <div style="font-size:8.5px; font-weight:normal; margin-top:1px;">AgentOps & LangSmith Observability</div>
    </div>
  </div>
</body>
</html>`;
  };

  const handleDownloadPDF = () => {
    if (!dossier) return;
    try {
      const printIframe = document.createElement("iframe");
      printIframe.name = "dossier_print_frame";
      printIframe.style.position = "fixed";
      printIframe.style.top = "-10000px";
      printIframe.style.left = "-10000px";
      printIframe.style.width = "0";
      printIframe.style.height = "0";
      printIframe.style.border = "none";
      document.body.appendChild(printIframe);

      const frameDoc = printIframe.contentWindow || printIframe.contentDocument.document || printIframe.contentDocument;
      frameDoc.document.open();
      frameDoc.document.write(generatePrintableHtml());
      frameDoc.document.close();

      setTimeout(() => {
        try {
          frameDoc.focus();
          frameDoc.print();
        } catch (printErr) {
          console.warn("Direct iframe print failed, falling back to window.open:", printErr);
          const w = window.open("", "_blank");
          if (w) {
            w.document.write(generatePrintableHtml());
            w.document.close();
            w.focus();
            w.print();
          }
        } finally {
          setTimeout(() => {
            if (document.body.contains(printIframe)) {
              document.body.removeChild(printIframe);
            }
          }, 2000);
        }
      }, 350);
    } catch (e) {
      console.error("Error generating printable dossier:", e);
      const w = window.open("", "_blank");
      if (w) {
        w.document.write(generatePrintableHtml());
        w.document.close();
        w.focus();
        w.print();
      }
    }
  };

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
                <span className="dd-property-price-tag">{formatMillionPrice(propertyPrice)}</span>
                {(userWallet?.balance_vnd !== undefined || userWallet?.balance !== undefined) && (
                  <span className="dd-property-tag" title="Số dư ví AI">
                    <Wallet size={11} /> {formatVND(userWallet?.balance_vnd ?? userWallet?.balance)}
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
                      <b>{Math.round(equityRatio * 100)}% ({formatMillionPrice(equityCapital)})</b>
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
                      <b>{formatMillionPrice(loanAmount)}</b>
                    </div>
                    <div className="dd-loan-item">
                      <span>Gốc + Lãi tháng đầu (ước tính):</span>
                      <b style={{ color: "#2563eb" }}>{formatMillionPrice(estimatedMonth1Payment, "triệu đ/tháng")}</b>
                    </div>
                    <div className="dd-loan-item" style={{ fontSize: "11px", color: "#94a3b8" }}>
                      <span>Lãi suất tham chiếu:</span>
                      <span>8.5%/năm • 20 năm</span>
                    </div>
                  </div>
                </div>

                {/* Deep Research Toggle Card */}
                <div className="dd-deep-research-toggle-card">
                  <div className="dd-deep-research-header">
                    <label className="dd-toggle-switch">
                      <input
                        type="checkbox"
                        checked={enableDeepResearch}
                        disabled={isAnalyzing}
                        onChange={(e) => setEnableDeepResearch(e.target.checked)}
                      />
                      <span className="dd-toggle-slider"></span>
                    </label>
                    <div className="dd-toggle-info">
                      <div className="dd-toggle-title">
                        <Search size={15} style={{ color: "#2563eb" }} />
                        <span>Kích hoạt Deep Research (Điều tra sâu chủ đầu tư & lịch sử tranh chấp)</span>
                        <span className="dd-pill-hybrid">Hybrid Deep Agent</span>
                      </div>
                      <p className="dd-toggle-desc">
                        Tác tử tự trị sẽ quét sâu báo chí, cổng pháp lý và diễn đàn để phát hiện rủi ro chậm cấp sổ đỏ, khiếu nại cư dân hoặc thế chấp ngân hàng.
                      </p>
                    </div>
                  </div>

                  {enableDeepResearch && (
                    <div className="dd-deep-research-inputs">
                      <label style={{ fontSize: "12px", fontWeight: 600, color: "#334155" }}>
                        Tên Chủ đầu tư / Dự án cần điều tra:
                      </label>
                      <input
                        type="text"
                        className="dd-input-text"
                        placeholder="VD: Sun Group, FPT City, Đất Xanh Miền Trung, The Royal..."
                        value={developerName}
                        disabled={isAnalyzing}
                        onChange={(e) => setDeveloperName(e.target.value)}
                      />
                    </div>
                  )}
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
              {isCached && (
                <div style={{
                  background: "rgba(56, 189, 248, 0.12)",
                  border: "1px solid rgba(56, 189, 248, 0.35)",
                  borderRadius: "10px",
                  padding: "12px 18px",
                  marginBottom: "16px",
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  fontSize: "0.88rem",
                  color: "#38bdf8"
                }}>
                  <Zap size={20} style={{ color: "#f59e0b", flexShrink: 0 }} />
                  <div>
                    <strong>🎯 Kết Quả Tái Sử Dụng Từ Kho Cache:</strong> Bất động sản này đã được thẩm định trong thời gian hiệu lực gần đây. Hệ thống tải ngay kết quả tức khắc và <strong>miễn phí 100%</strong> chi phí chạy lại.
                  </div>
                </div>
              )}

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
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap", marginBottom: "4px" }}>
                    <div className={`dd-verdict-pill ${verdictColorClass}`}>
                      <VerdictIcon size={14} />
                      <span>{verdictText}</span>
                    </div>
                    <button
                      type="button"
                      className="dd-btn-download-pdf-compact"
                      onClick={handleDownloadPDF}
                      title="Tải xuống toàn bộ hồ sơ thẩm định định dạng PDF"
                    >
                      <Download size={13} />
                      <span>Xuất PDF</span>
                    </button>
                  </div>

                  <div className="dd-exec-summary-box">
                    {formatFriendlyText(dossier.executive_summary)}
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

                {dossier?.deep_research && (
                  <button
                    type="button"
                    className={`dd-tab-btn ${activeTab === "deep_research" ? "active" : ""}`}
                    onClick={() => setActiveTab("deep_research")}
                    style={{ borderColor: "#38bdf8" }}
                  >
                    <Search size={14} style={{ color: "#0284c7" }} />
                    <span style={{ fontWeight: 600 }}>Deep Research</span>
                    <span className="dd-pill-hybrid-badge">AI</span>
                  </button>
                )}

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
                      <div className="dd-metric-val">{formatMillionPerM2(dossier.valuation?.unit_price_per_m2)}</div>
                      <div className="dd-metric-sub">
                        Trung bình quận: {formatMillionPerM2(dossier.valuation?.avg_district_price_per_m2)}
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
                      {formatFriendlyText(dossier.executive_summary)}
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
                        {formatMillionPerM2(dossier.valuation?.unit_price_per_m2)}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: "12px", color: "#64748b", marginBottom: "4px" }}>Mặt bằng trung bình khu vực quận:</div>
                      <div style={{ fontSize: "20px", fontWeight: 800, color: "#2563eb" }}>
                        {formatMillionPerM2(dossier.valuation?.avg_district_price_per_m2)}
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
                              <th>Tổng giá</th>
                              <th>Đơn giá / m²</th>
                            </tr>
                          </thead>
                          <tbody>
                            {dossier.valuation.comparable_properties.map((comp, idx) => (
                              <tr key={idx}>
                                <td style={{ fontWeight: 600 }}>{comp.title}</td>
                                <td>{comp.area} m²</td>
                                <td>{formatMillionPrice(comp.price)}</td>
                                <td style={{ color: "#2563eb", fontWeight: 700 }}>
                                  {formatMillionPerM2(comp.unit_price_per_m2)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Tin đăng thực tế từ Web (Tavily Search) */}
                  {dossier.valuation?.live_market_listings && dossier.valuation.live_market_listings.length > 0 && (
                    <div style={{ marginTop: "20px" }}>
                      <div style={{ fontSize: "13px", fontWeight: 700, color: "#1e293b", marginBottom: "10px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <Globe size={15} style={{ color: "#0284c7" }} />
                        <span>Tin đăng thị trường thực tế tham khảo qua Web (Tavily Search - {dossier.valuation.live_market_listings.length} tin):</span>
                      </div>
                      <div className="dd-web-listings-grid">
                        {dossier.valuation.live_market_listings.map((item, idx) => (
                          <div key={idx} className="dd-web-listing-card">
                            <div className="dd-web-listing-header">
                              <span className="dd-web-listing-badge">{item.source_domain || "web"}</span>
                              {item.url && (
                                <a
                                  href={item.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="dd-web-listing-link"
                                  title="Mở tin đăng gốc trên trang web"
                                >
                                  <span>Xem tin gốc</span>
                                  <ExternalLink size={12} />
                                </a>
                              )}
                            </div>
                            <div className="dd-web-listing-title">{item.title}</div>
                            {item.snippet && (
                              <div className="dd-web-listing-snippet">{item.snippet}</div>
                            )}
                          </div>
                        ))}
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
                      <div className="dd-metric-val">{formatMillionPrice(dossier.financial?.loan_amount_vnd ?? loanAmount)}</div>
                      <div className="dd-metric-sub">Vốn tự có: {formatMillionPrice(equityCapital)}</div>
                    </div>

                    <div className="dd-metric-card">
                      <div className="dd-metric-title">
                        <Calculator size={14} /> Trả góp tháng đầu
                      </div>
                      <div className="dd-metric-val" style={{ color: "#2563eb" }}>
                        {formatMillionPrice(dossier.financial?.monthly_repayment_vnd, "triệu đ/tháng")}
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
                        {formatMillionPrice(dossier.financial?.estimated_monthly_rental_income, "triệu đ/tháng")}
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

              {/* Tab: Deep Developer & Dispute Investigation (Deep Research) */}
              {activeTab === "deep_research" && dossier.deep_research && (
                <div className="dd-tab-pane">
                  <div className="dd-dr-overview-card">
                    <div className="dd-dr-header">
                      <div>
                        <div className="dd-dr-target-title">
                          <Search size={18} style={{ color: "#0284c7" }} />
                          <span>Đối tượng điều tra: {dossier.deep_research.target_entity}</span>
                        </div>
                        {dossier.deep_research.developer_name && (
                          <div className="dd-dr-dev-sub">
                            Chủ đầu tư / Đơn vị phát triển: <b>{dossier.deep_research.developer_name}</b>
                          </div>
                        )}
                      </div>
                      <div className="dd-dr-score-badge">
                        <div className="dd-dr-score-num">{dossier.deep_research.reputation_score}</div>
                        <div className="dd-dr-score-label">Điểm tín nhiệm / 100</div>
                      </div>
                    </div>

                    <div className="dd-dr-summary-box">
                      <p><b>Tóm tắt năng lực bàn giao & lịch sử:</b> {dossier.deep_research.track_record_summary}</p>
                      <div className="dd-dr-sentiment-tag">
                        Đánh giá cộng đồng: <span className={`dd-sentiment-${dossier.deep_research.community_sentiment}`}>
                          {dossier.deep_research.community_sentiment?.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Red Flags Alert */}
                  {dossier.deep_research.red_flags && dossier.deep_research.red_flags.length > 0 && (
                    <div className="dd-dr-section dd-dr-red-flags">
                      <div className="dd-dr-section-title" style={{ color: "#b91c1c" }}>
                        <ShieldAlert size={16} />
                        <span>Cảnh báo rủi ro đỏ (Red Flags):</span>
                      </div>
                      <div className="dd-dr-list">
                        {dossier.deep_research.red_flags.map((flag, idx) => (
                          <div key={idx} className="dd-dr-item dd-dr-flag-item">
                            <AlertTriangle size={15} style={{ color: "#ef4444", flexShrink: 0, marginTop: "2px" }} />
                            <span>{flag}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Dispute History */}
                  {dossier.deep_research.dispute_history && dossier.deep_research.dispute_history.length > 0 && (
                    <div className="dd-dr-section dd-dr-disputes">
                      <div className="dd-dr-section-title" style={{ color: "#c2410c" }}>
                        <Scale size={16} />
                        <span>Tiền sử tranh chấp & Khiếu nại pháp lý:</span>
                      </div>
                      <div className="dd-dr-list">
                        {dossier.deep_research.dispute_history.map((disp, idx) => (
                          <div key={idx} className="dd-dr-item dd-dr-dispute-item">
                            <span className="dd-bullet-orange">•</span>
                            <span>{disp}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Sources Analyzed */}
                  {dossier.deep_research.sources_analyzed && dossier.deep_research.sources_analyzed.length > 0 && (
                    <div className="dd-dr-section">
                      <div className="dd-dr-section-title" style={{ color: "#334155" }}>
                        <Globe size={16} />
                        <span>Nguồn tin & Cổng pháp lý đã rà soát ({dossier.deep_research.sources_analyzed.length} nguồn):</span>
                      </div>
                      <div className="dd-dr-sources-grid">
                        {dossier.deep_research.sources_analyzed.map((src, idx) => (
                          <a
                            key={idx}
                            href={src.url || "#"}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="dd-dr-source-card"
                          >
                            <span className="dd-dr-source-title">{src.title || "Tin bài rà soát"}</span>
                            <ExternalLink size={12} style={{ color: "#94a3b8" }} />
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
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

                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <button
                          type="button"
                          className="dd-btn-download-pdf"
                          onClick={handleDownloadPDF}
                          title="Tải xuống toàn bộ hồ sơ thẩm định định dạng PDF"
                        >
                          <Download size={14} />
                          <span>Tải xuống PDF</span>
                        </button>

                        <button
                          type="button"
                          className={`dd-btn-copy-markdown ${copiedMarkdown ? "copied" : ""}`}
                          onClick={handleCopyMarkdown}
                          title="Sao chép toàn bộ văn bản Markdown"
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
                    </div>

                    <div className="dd-markdown-rendered-view">
                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                        {formatFriendlyText(dossier.full_markdown_report || "Báo cáo đang được tổng hợp...")}
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
