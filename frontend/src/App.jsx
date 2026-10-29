import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Building2,
  MapPin,
  Bed,
  Maximize2,
  CheckCircle2,
  X,
  Plus,
  MessageSquare,
  Trash2,
  Scale,
  FileText,
  UploadCloud,
  Eye,
  Check,
  AlertCircle,
  Database,
  ArrowRight
} from "lucide-react";

const INITIAL_GREETING = {
  sender: "bot",
  text: "Xin chào anh/chị! Em là trợ lý tư vấn Bất động sản và Pháp lý nhà ở tại Đà Nẵng. Anh/chị đang có nhu cầu thuê/mua nhà đất hay cần tư vấn về thủ tục pháp lý, sổ đỏ, hợp đồng đặt cọc ạ?",
  properties: [],
  citations: []
};

const createNewThreadObject = () => {
  const id = "session_" + Date.now().toString(36) + "_" + Math.random().toString(36).substring(2, 6);
  return {
    id,
    title: "Cuộc trò chuyện mới",
    messages: [INITIAL_GREETING],
    createdAt: Date.now()
  };
};

const STORAGE_KEY = "danang_re_threads";
const ACTIVE_THREAD_KEY = "danang_re_active_thread_id";

export default function App() {
  // Navigation: "chat" | "admin_legal"
  const [activeTab, setActiveTab] = useState("chat");

  // 1. Quản lý danh sách threads & thread đang active
  const [threads, setThreads] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) {
      console.error("Lỗi đọc threads từ localStorage:", e);
    }
    return [createNewThreadObject()];
  });

  const [activeThreadId, setActiveThreadId] = useState(() => {
    try {
      const savedActive = localStorage.getItem(ACTIVE_THREAD_KEY);
      if (savedActive) return savedActive;
    } catch (e) {
      console.error(e);
    }
    return "";
  });

  useEffect(() => {
    if (!activeThreadId && threads.length > 0) {
      setActiveThreadId(threads[0].id);
    }
  }, [threads, activeThreadId]);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(threads));
    } catch (e) {
      console.error("Lỗi lưu threads:", e);
    }
  }, [threads]);

  useEffect(() => {
    if (activeThreadId) {
      localStorage.setItem(ACTIVE_THREAD_KEY, activeThreadId);
    }
  }, [activeThreadId]);

  const activeThread = threads.find((t) => t.id === activeThreadId) || threads[0];
  const messages = activeThread?.messages || [];

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [leadForm, setLeadForm] = useState({ name: "", phone: "", note: "" });
  const [leadSuccess, setLeadSuccess] = useState(false);

  // Drawer căn cứ pháp lý
  const [activeDrawerCitations, setActiveDrawerCitations] = useState(null);
  const [selectedCitationIndex, setSelectedCitationIndex] = useState(1);

  // Quản trị tài liệu pháp lý (Admin)
  const [legalDocs, setLegalDocs] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [adminMessage, setAdminMessage] = useState(null);
  const [previewDoc, setPreviewDoc] = useState(null);
  const fileInputRef = useRef(null);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load danh sách tài liệu khi mở tab admin
  useEffect(() => {
    if (activeTab === "admin_legal") {
      fetchLegalDocs();
    }
  }, [activeTab]);

  const fetchLegalDocs = async () => {
    setLoadingDocs(true);
    try {
      const res = await fetch("http://localhost:8000/api/legal/documents");
      const json = await res.json();
      if (json.success) {
        setLegalDocs(json.data || []);
      }
    } catch (err) {
      console.error("Lỗi tải danh sách tài liệu:", err);
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleCreateNewThread = () => {
    const newThread = createNewThreadObject();
    setThreads((prev) => [newThread, ...prev]);
    setActiveThreadId(newThread.id);
    setInput("");
  };

  const handleDeleteThread = (e, threadIdToDelete) => {
    e.stopPropagation();
    setThreads((prev) => {
      const filtered = prev.filter((t) => t.id !== threadIdToDelete);
      if (filtered.length === 0) {
        const freshThread = createNewThreadObject();
        setActiveThreadId(freshThread.id);
        return [freshThread];
      }
      if (activeThreadId === threadIdToDelete) {
        setActiveThreadId(filtered[0].id);
      }
      return filtered;
    });
  };

  const updateActiveThreadMessages = (updateFn) => {
    setThreads((prev) =>
      prev.map((t) => {
        if (t.id !== activeThreadId) return t;
        const updatedMsgs = updateFn(t.messages);
        let title = t.title;
        if (title === "Cuộc trò chuyện mới" && updatedMsgs.length > 1) {
          const firstUserMsg = updatedMsgs.find((m) => m.sender === "user");
          if (firstUserMsg && firstUserMsg.text) {
            title = firstUserMsg.text.length > 28
              ? firstUserMsg.text.substring(0, 28) + "..."
              : firstUserMsg.text;
          }
        }
        return { ...t, title, messages: updatedMsgs };
      })
    );
  };

  const handleSend = async (textToSend) => {
    const query = textToSend || input;
    if (!query.trim() || loading || !activeThreadId) return;

    const userMsg = { sender: "user", text: query, properties: [], citations: [] };
    updateActiveThreadMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch("http://localhost:8000/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query, thread_id: activeThreadId }),
      });

      if (!response.body) throw new Error("Không nhận được luồng stream");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let botMsg = { sender: "bot", text: "", properties: [], citations: [] };

      updateActiveThreadMessages((prev) => [...prev, botMsg]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const raw = line.replace("data: ", "").trim();
            if (raw === "[DONE]") break;

            try {
              const data = JSON.parse(raw);
              if (data.type === "token") {
                botMsg.text += data.content;
                updateActiveThreadMessages((prev) => [...prev.slice(0, -1), { ...botMsg }]);
              } else if (data.type === "properties") {
                botMsg.properties = data.data;
                updateActiveThreadMessages((prev) => [...prev.slice(0, -1), { ...botMsg }]);
              } else if (data.type === "citations") {
                botMsg.citations = data.data;
                updateActiveThreadMessages((prev) => [...prev.slice(0, -1), { ...botMsg }]);
              } else if (data.type === "error") {
                botMsg.text = "Lỗi xử lý: " + data.content;
                updateActiveThreadMessages((prev) => [...prev.slice(0, -1), { ...botMsg }]);
              }
            } catch (err) {
              console.error("Parse JSON stream error:", err);
            }
          }
        }
      }
    } catch (error) {
      console.error("Lỗi gửi tin:", error);
      updateActiveThreadMessages((prev) => [
        ...prev,
        {
          sender: "bot",
          text: "Dạ hiện tại không thể kết nối tới Backend FastAPI (cổng 8000). Anh/chị kiểm tra lại service nhé!",
          properties: [],
          citations: []
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleBookVisit = (prop) => {
    setSelectedProperty(prop);
    setLeadSuccess(false);
    setLeadForm({ name: "", phone: "", note: "" });
  };

  const submitLead = async (e) => {
    e.preventDefault();
    if (!leadForm.name || !leadForm.phone) return;

    try {
      await fetch("http://localhost:8000/api/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...leadForm,
          property_id: selectedProperty?.id || "general"
        })
      });
      setLeadSuccess(true);
      setTimeout(() => {
        setSelectedProperty(null);
        setLeadSuccess(false);
      }, 2000);
    } catch (err) {
      alert("Lỗi gửi liên hệ: " + err.message);
    }
  };

  // Mở Drawer hiển thị căn cứ pháp lý
  const handleOpenCitation = (index, citationsList) => {
    setActiveDrawerCitations(citationsList);
    setSelectedCitationIndex(index);
  };

  // Render text có chèn các badge trích dẫn [1], [2] tương tác
  const renderMessageContent = (msg) => {
    if (!msg.text) return null;
    const citations = msg.citations || [];

    // Tách văn bản theo pattern [1], [2],...
    const parts = msg.text.split(/(\[\d+\])/g);

    return (
      <div>
        <div className="bubble">
          {parts.map((part, i) => {
            const match = part.match(/^\[(\d+)\]$/);
            if (match) {
              const num = parseInt(match[1], 10);
              return (
                <button
                  key={i}
                  className="citation-badge"
                  onClick={() => handleOpenCitation(num, citations)}
                  title="Bấm để xem căn cứ pháp lý đối chiếu"
                >
                  [{num}]
                </button>
              );
            }
            return <span key={i}>{part}</span>;
          })}
        </div>

        {/* Nút footer xem căn cứ pháp lý nếu câu trả lời có citations */}
        {citations.length > 0 && (
          <button
            className="citations-footer-btn"
            onClick={() => handleOpenCitation(1, citations)}
          >
            <Scale size={14} /> Xem {citations.length} căn cứ pháp lý đã trích dẫn
          </button>
        )}
      </div>
    );
  };

  // ==================== CÁC HÀM XỬ LÝ ADMIN TÀI LIỆU ====================
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setAdminMessage({ type: "info", text: `Đang upload & chuyển đổi "${file.name}" sang Markdown...` });

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/api/legal/upload", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload thất bại");

      setAdminMessage({
        type: "success",
        text: `Đã tải lên và chuẩn hóa thành công: "${file.name}". Vui lòng bấm "Nạp Vector" để nạp vào Qdrant.`
      });
      fetchLegalDocs();
    } catch (err) {
      setAdminMessage({ type: "error", text: "Lỗi upload: " + err.message });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleIndexDoc = async (docId) => {
    setAdminMessage({ type: "info", text: "Đang cắt đoạn theo Điều/Khoản và tính embeddings nạp vào Qdrant..." });
    try {
      const res = await fetch(`http://localhost:8000/api/legal/documents/${docId}/index`, {
        method: "POST"
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Index thất bại");

      setAdminMessage({ type: "success", text: data.message });
      fetchLegalDocs();
    } catch (err) {
      setAdminMessage({ type: "error", text: "Lỗi index: " + err.message });
    }
  };

  const handleDeleteDoc = async (docId, title) => {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa tài liệu: "${title}" cùng toàn bộ vector liên quan?`)) return;

    try {
      const res = await fetch(`http://localhost:8000/api/legal/documents/${docId}`, {
        method: "DELETE"
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Xóa thất bại");

      setAdminMessage({ type: "success", text: "Đã xóa tài liệu thành công!" });
      fetchLegalDocs();
    } catch (err) {
      setAdminMessage({ type: "error", text: "Lỗi xóa: " + err.message });
    }
  };

  const handlePreviewDoc = async (docId, title) => {
    try {
      const res = await fetch(`http://localhost:8000/api/legal/documents/${docId}/preview`);
      const data = await res.json();
      if (data.success) {
        setPreviewDoc({ id: docId, title, content: data.data.content });
      }
    } catch (err) {
      alert("Lỗi tải bản xem trước: " + err.message);
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="brand-header">
          <div className="brand-badge">
            <Building2 size={24} />
          </div>
          <div>
            <div className="brand-title">Đà Nẵng BĐS & Luật AI</div>
            <div className="brand-subtitle">Tư vấn Nhà đất & Pháp lý</div>
          </div>
        </div>

        {/* Quản lý Thread */}
        <div className="thread-section">
          <button className="btn-new-thread" onClick={handleCreateNewThread}>
            <Plus size={16} /> Tạo đoạn chat mới
          </button>

          <div className="threads-header">
            <span>Lịch sử hội thoại</span>
          </div>

          <div className="thread-list">
            {threads.map((t) => (
              <div
                key={t.id}
                className={`thread-item ${t.id === activeThreadId ? "active" : ""}`}
                onClick={() => {
                  setActiveThreadId(t.id);
                  setActiveTab("chat");
                }}
              >
                <div className="thread-info">
                  <MessageSquare size={14} style={{ flexShrink: 0 }} />
                  <span className="thread-title">{t.title}</span>
                </div>
                {threads.length > 1 && (
                  <button
                    className="btn-delete-thread"
                    title="Xóa hội thoại"
                    onClick={(e) => handleDeleteThread(e, t.id)}
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Gợi ý tìm nhanh & Câu hỏi pháp lý */}
        <div className="quick-prompts">
          <h4>Gợi ý tra cứu nhanh</h4>
          <button
            className="prompt-btn"
            onClick={() => {
              setActiveTab("chat");
              handleSend("Người nước ngoài có được mua và sở hữu căn hộ chung cư tại Đà Nẵng không?");
            }}
          >
            ⚖️ Người nước ngoài mua chung cư ĐN
          </button>
          <button
            className="prompt-btn"
            onClick={() => {
              setActiveTab("chat");
              handleSend("Điều kiện để nhà ở thương mại được phép mua bán theo Luật Nhà ở mới nhất?");
            }}
          >
            📜 Điều kiện mua bán nhà ở thương mại
          </button>
          <button
            className="prompt-btn"
            onClick={() => {
              setActiveTab("chat");
              handleSend("Quy định về mức tiền đặt cọc tối đa khi mua nhà dự án?");
            }}
          >
            📝 Quy định tiền đặt cọc mua nhà
          </button>
          <button
            className="prompt-btn"
            onClick={() => {
              setActiveTab("chat");
              handleSend("Tìm thuê căn hộ 2 phòng ngủ Sơn Trà view sông Hàn dưới 15 triệu");
            }}
          >
            🏢 Căn hộ 2PN Sơn Trà view sông Hàn
          </button>
        </div>
      </div>

      {/* Main Area: Chuyển đổi giữa Chat và Quản Trị Pháp Lý */}
      {activeTab === "chat" ? (
        <div className="chat-main">
          {/* Header với Navigation Switcher */}
          <div className="chat-header">
            <div>
              <h3 style={{ fontSize: "16px", fontWeight: "700" }}>
                {activeThread?.title || "Trợ lý AI Nhà Đất & Pháp Lý Đà Nẵng"}
              </h3>
              <p style={{ fontSize: "12px", color: "#64748b" }}>
                ID phiên: <code style={{ background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px" }}>{activeThreadId}</code>
              </p>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
              <div className="header-nav">
                <button
                  className={`nav-tab-btn ${activeTab === "chat" ? "active" : ""}`}
                  onClick={() => setActiveTab("chat")}
                >
                  <MessageSquare size={14} /> Tư Vấn BĐS
                </button>
                <button
                  className={`nav-tab-btn ${activeTab === "admin_legal" ? "active" : ""}`}
                  onClick={() => setActiveTab("admin_legal")}
                >
                  <Scale size={14} /> Quản Trị Pháp Lý
                </button>
              </div>

              <div className="status-badge">
                <div className="status-dot"></div> Sẵn sàng tư vấn
              </div>
            </div>
          </div>

          {/* Danh sách tin nhắn */}
          <div className="message-list">
            {messages.map((msg, idx) => (
              <div key={idx} className={`message-row ${msg.sender}`}>
                <div className={`avatar ${msg.sender}`}>
                  {msg.sender === "bot" ? <Building2 size={18} /> : "Bạn"}
                </div>
                <div className="message-content">
                  {msg.sender === "bot" ? renderMessageContent(msg) : <div className="bubble">{msg.text}</div>}

                  {/* Property Carousel Cards */}
                  {msg.properties && msg.properties.length > 0 && (
                    <div className="cards-scroll-container">
                      {msg.properties.map((item) => (
                        <div key={item.id} className="property-card">
                          <img src={item.image} alt={item.title} className="card-img" />
                          <div className="card-body">
                            <span className="card-badge">
                              <MapPin size={10} style={{ display: "inline", marginRight: "3px" }} />
                              {item.ward ? `${item.ward}, ` : ""}{item.district}
                            </span>
                            <h4 className="card-title">{item.title}</h4>
                            <div className="card-price">
                              {item.price ? `${item.price.toLocaleString("vi-VN")} VNĐ` : "Thỏa thuận"}
                              {item.category === "rent" ? "/tháng" : ""}
                            </div>
                            <div className="card-meta">
                              {item.bedrooms > 0 && (
                                <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                  <Bed size={14} /> {item.bedrooms} PN
                                </span>
                              )}
                              <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                <Maximize2 size={14} /> {item.area_m2} m²
                              </span>
                            </div>
                            <button className="btn-book" onClick={() => handleBookVisit(item)}>
                              Đặt lịch xem nhà
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Bar */}
          <div className="chat-input-bar">
            <form
              className="input-container"
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
            >
              <input
                type="text"
                placeholder="Hỏi về pháp lý, sổ đỏ, đặt cọc hoặc tìm thuê/mua nhà đất Đà Nẵng..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
              />
              <button type="submit" className="btn-send" disabled={loading}>
                <Send size={18} />
              </button>
            </form>
          </div>
        </div>
      ) : (
        /* ==================== MÀN HÌNH QUẢN TRỊ TÀI LIỆU PHÁP LÝ ==================== */
        <div className="admin-view-container">
          <div className="admin-header">
            <div>
              <h2 style={{ fontSize: "20px", fontWeight: "700", color: "#0f172a" }}>
                Quản Trị Cơ Sở Dữ Liệu Pháp Lý Nhà Ở
              </h2>
              <p style={{ fontSize: "13px", color: "#64748b", marginTop: "4px" }}>
                Tải lên file PDF, Word (.docx) hoặc Markdown (.md). Hệ thống tự động chuyển đổi sang Markdown và nạp vector vào Qdrant.
              </p>
            </div>

            <div className="header-nav">
              <button className="nav-tab-btn" onClick={() => setActiveTab("chat")}>
                <MessageSquare size={14} /> Về Khung Chat
              </button>
              <button className="nav-tab-btn active">
                <Scale size={14} /> Quản Trị Pháp Lý
              </button>
            </div>
          </div>

          {/* Thông báo Admin */}
          {adminMessage && (
            <div
              style={{
                padding: "12px 16px",
                borderRadius: "10px",
                marginBottom: "20px",
                fontSize: "13px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background:
                  adminMessage.type === "success" ? "#ecfdf5" : adminMessage.type === "error" ? "#fef2f2" : "#eff6ff",
                color:
                  adminMessage.type === "success" ? "#065f46" : adminMessage.type === "error" ? "#991b1b" : "#1e40af",
                border: `1px solid ${
                  adminMessage.type === "success" ? "#a7f3d0" : adminMessage.type === "error" ? "#fecaca" : "#bfdbfe"
                }`
              }}
            >
              <span>{adminMessage.text}</span>
              <button
                onClick={() => setAdminMessage(null)}
                style={{ border: "none", background: "transparent", cursor: "pointer", color: "inherit" }}
              >
                <X size={16} />
              </button>
            </div>
          )}

          {/* Stats Grid */}
          <div className="admin-stats-grid">
            <div className="admin-stat-card">
              <div style={{ background: "#dbeafe", color: "#2563eb", padding: "10px", borderRadius: "10px" }}>
                <FileText size={22} />
              </div>
              <div>
                <div style={{ fontSize: "12px", color: "#64748b" }}>Tổng số tài liệu</div>
                <div style={{ fontSize: "20px", fontWeight: "700", color: "#0f172a" }}>{legalDocs.length}</div>
              </div>
            </div>

            <div className="admin-stat-card">
              <div style={{ background: "#dcfce7", color: "#16a34a", padding: "10px", borderRadius: "10px" }}>
                <Database size={22} />
              </div>
              <div>
                <div style={{ fontSize: "12px", color: "#64748b" }}>Tổng số đoạn (Chunks)</div>
                <div style={{ fontSize: "20px", fontWeight: "700", color: "#0f172a" }}>
                  {legalDocs.reduce((acc, d) => acc + (d.chunks_count || 0), 0)}
                </div>
              </div>
            </div>

            <div className="admin-stat-card">
              <div style={{ background: "#fef3c7", color: "#d97706", padding: "10px", borderRadius: "10px" }}>
                <Scale size={22} />
              </div>
              <div>
                <div style={{ fontSize: "12px", color: "#64748b" }}>Vector Collection</div>
                <div style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a" }}>danang_legal_docs</div>
              </div>
            </div>
          </div>

          {/* Vùng Upload Dropzone */}
          <div className="admin-upload-zone" onClick={() => fileInputRef.current?.click()}>
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: "none" }}
              accept=".pdf,.docx,.md,.markdown,.txt"
              onChange={handleFileUpload}
            />
            <UploadCloud size={40} color="#2563eb" style={{ margin: "0 auto 10px" }} />
            <h4 style={{ fontSize: "15px", fontWeight: "700", color: "#0f172a", marginBottom: "6px" }}>
              {uploading ? "Đang xử lý tài liệu..." : "Tải lên văn bản pháp lý mới"}
            </h4>
            <p style={{ fontSize: "13px", color: "#64748b" }}>
              Hỗ trợ định dạng <b>.pdf</b>, <b>.docx</b> (Word) và <b>.md</b> (Markdown). Hệ thống tự động chuyển đổi sang Markdown chuẩn.
            </p>
          </div>

          {/* Bảng danh sách tài liệu */}
          <div className="legal-table-container">
            <div style={{ padding: "16px 20px", borderBottom: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h4 style={{ fontSize: "14px", fontWeight: "700", color: "#0f172a" }}>
                Danh Sách Văn Bản Quy Phạm Pháp Luật
              </h4>
              <button
                onClick={fetchLegalDocs}
                style={{
                  background: "#f1f5f9",
                  border: "none",
                  padding: "6px 12px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  cursor: "pointer",
                  fontWeight: "600"
                }}
              >
                Làm mới
              </button>
            </div>

            <table className="legal-table">
              <thead>
                <tr>
                  <th>Tên văn bản</th>
                  <th>Tập tin gốc</th>
                  <th>Kích thước</th>
                  <th>Ngày nạp</th>
                  <th>Trạng thái</th>
                  <th>Số Chunks</th>
                  <th style={{ textAlign: "right" }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {legalDocs.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", padding: "30px", color: "#94a3b8" }}>
                      Chưa có tài liệu pháp lý nào. Hãy tải lên tài liệu đầu tiên!
                    </td>
                  </tr>
                ) : (
                  legalDocs.map((doc) => (
                    <tr key={doc.id}>
                      <td style={{ fontWeight: "600", color: "#0f172a" }}>{doc.title || doc.filename}</td>
                      <td>
                        <span style={{ background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px", fontSize: "11px" }}>
                          {doc.filename}
                        </span>
                      </td>
                      <td>{(doc.size / 1024).toFixed(1)} KB</td>
                      <td>{doc.uploaded_at}</td>
                      <td>
                        {doc.status === "indexed" ? (
                          <span className="badge-status badge-indexed">
                            <Check size={12} style={{ marginRight: "3px" }} /> Đã Index
                          </span>
                        ) : (
                          <span className="badge-status badge-pending">
                            <AlertCircle size={12} style={{ marginRight: "3px" }} /> Chờ Index
                          </span>
                        )}
                      </td>
                      <td><b>{doc.chunks_count || 0}</b></td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          className="btn-action"
                          style={{ background: "#e0f2fe", color: "#0369a1" }}
                          onClick={() => handlePreviewDoc(doc.id, doc.title || doc.filename)}
                          title="Xem trước Markdown"
                        >
                          <Eye size={12} /> Xem
                        </button>
                        <button
                          className="btn-action"
                          style={{ background: "#dcfce7", color: "#15803d" }}
                          onClick={() => handleIndexDoc(doc.id)}
                          title="Cắt đoạn và nạp Vector vào Qdrant"
                        >
                          <Database size={12} /> Nạp Vector
                        </button>
                        <button
                          className="btn-action"
                          style={{ background: "#fee2e2", color: "#b91c1c" }}
                          onClick={() => handleDeleteDoc(doc.id, doc.title || doc.filename)}
                          title="Xóa tài liệu"
                        >
                          <Trash2 size={12} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ==================== RIGHT-SIDE DRAWER CĂN CỨ PHÁP LÝ ==================== */}
      {activeDrawerCitations && activeDrawerCitations.length > 0 && (
        <div className="citations-drawer-overlay" onClick={() => setActiveDrawerCitations(null)}>
          <div className="citations-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <div style={{ background: "#dbeafe", color: "#2563eb", padding: "8px", borderRadius: "8px" }}>
                  <Scale size={20} />
                </div>
                <div>
                  <h3 style={{ fontSize: "15px", fontWeight: "700", color: "#0f172a" }}>Căn Cứ Pháp Lý Đối Chiếu</h3>
                  <p style={{ fontSize: "12px", color: "#64748b" }}>Trích xuất từ Qdrant Vector DB</p>
                </div>
              </div>
              <button
                onClick={() => setActiveDrawerCitations(null)}
                style={{ border: "none", background: "transparent", cursor: "pointer", color: "#64748b" }}
              >
                <X size={20} />
              </button>
            </div>

            <div className="drawer-body">
              {/* Pills chuyển đổi trích dẫn [1], [2],... */}
              <div className="citation-tabs">
                {activeDrawerCitations.map((item, i) => {
                  const idx = item.index || i + 1;
                  return (
                    <button
                      key={idx}
                      className={`citation-tab-pill ${selectedCitationIndex === idx ? "active" : ""}`}
                      onClick={() => setSelectedCitationIndex(idx)}
                    >
                      Trích dẫn [{idx}]
                    </button>
                  );
                })}
              </div>

              {/* Chi tiết trích dẫn đang chọn */}
              {(() => {
                const current =
                  activeDrawerCitations.find((c) => c.index === selectedCitationIndex) ||
                  activeDrawerCitations[0];
                if (!current) return null;

                return (
                  <div className="citation-detail-card">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                      <div>
                        <span style={{ fontSize: "11px", fontWeight: "700", color: "#2563eb", textTransform: "uppercase" }}>
                          Văn Bản Quy Phạm
                        </span>
                        <h4 style={{ fontSize: "15px", fontWeight: "700", color: "#0f172a", marginTop: "2px" }}>
                          {current.doc_title || "Văn bản Luật"}
                        </h4>
                      </div>
                      {current.score && (
                        <span
                          style={{
                            background: "#dcfce7",
                            color: "#15803d",
                            fontSize: "11px",
                            fontWeight: "700",
                            padding: "2px 8px",
                            borderRadius: "6px"
                          }}
                        >
                          Độ khớp: {Math.round(current.score * 100)}%
                        </span>
                      )}
                    </div>

                    {current.chapter && (
                      <div style={{ fontSize: "12px", color: "#475569", fontWeight: "600", marginBottom: "6px" }}>
                        {current.chapter}
                      </div>
                    )}

                    {current.article && (
                      <div style={{ fontSize: "13px", color: "#1e40af", fontWeight: "700", marginBottom: "12px" }}>
                        {current.article}
                      </div>
                    )}

                    <div
                      style={{
                        background: "#ffffff",
                        padding: "14px",
                        borderRadius: "8px",
                        border: "1px solid #e2e8f0",
                        fontSize: "13px",
                        lineHeight: "1.6",
                        color: "#334155",
                        whiteSpace: "pre-wrap"
                      }}
                    >
                      {current.content}
                    </div>

                    <div style={{ marginTop: "16px", fontSize: "12px", color: "#64748b" }}>
                      💡 <i>Căn cứ được dùng làm cơ sở suy luận cho câu trả lời của trợ lý AI.</i>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        </div>
      )}

      {/* ==================== MODAL PREVIEW MARKDOWN ==================== */}
      {previewDoc && (
        <div className="modal-overlay" onClick={() => setPreviewDoc(null)}>
          <div
            className="modal-card"
            style={{ width: "700px", maxWidth: "90vw", maxHeight: "85vh", display: "flex", flexDirection: "column" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: "700" }}>Xem trước: {previewDoc.title}</h3>
                <span style={{ fontSize: "12px", color: "#64748b" }}>Định dạng Markdown đã chuẩn hóa</span>
              </div>
              <button
                onClick={() => setPreviewDoc(null)}
                style={{ border: "none", background: "transparent", cursor: "pointer" }}
              >
                <X size={20} color="#64748b" />
              </button>
            </div>

            <div
              style={{
                flex: 1,
                overflowY: "auto",
                background: "#f8fafc",
                padding: "16px",
                borderRadius: "8px",
                border: "1px solid #e2e8f0",
                fontSize: "13px",
                lineHeight: "1.6",
                whiteSpace: "pre-wrap",
                fontFamily: "monospace"
              }}
            >
              {previewDoc.content}
            </div>

            <div style={{ marginTop: "16px", display: "flex", justifyContent: "flex-end" }}>
              <button
                className="btn-book"
                style={{ padding: "8px 16px" }}
                onClick={() => setPreviewDoc(null)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Lead Capture */}
      {selectedProperty && (
        <div className="modal-overlay" onClick={() => setSelectedProperty(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: "16px", fontWeight: "700" }}>Đặt lịch hẹn xem BĐS</h3>
              <button
                onClick={() => setSelectedProperty(null)}
                style={{ border: "none", background: "transparent", cursor: "pointer" }}
              >
                <X size={20} color="#64748b" />
              </button>
            </div>

            {leadSuccess ? (
              <div style={{ textAlign: "center", padding: "30px 0" }}>
                <CheckCircle2 size={48} color="#10b981" style={{ margin: "0 auto 12px" }} />
                <h4 style={{ color: "#0f172a", marginBottom: "6px" }}>Đặt lịch thành công!</h4>
                <p style={{ fontSize: "13px", color: "#64748b" }}>
                  Môi giới khu vực Đà Nẵng sẽ liên hệ lại với anh/chị trong ít phút.
                </p>
              </div>
            ) : (
              <form onSubmit={submitLead}>
                <div style={{ fontSize: "13px", color: "#2563eb", marginBottom: "16px", fontWeight: "600" }}>
                  BĐS: {selectedProperty.title}
                </div>
                <div className="form-group">
                  <label>Họ và tên của anh/chị</label>
                  <input
                    type="text"
                    required
                    placeholder="Nguyễn Văn A"
                    value={leadForm.name}
                    onChange={(e) => setLeadForm({ ...leadForm, name: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Số điện thoại / Zalo</label>
                  <input
                    type="tel"
                    required
                    placeholder="0905 xxx xxx"
                    value={leadForm.phone}
                    onChange={(e) => setLeadForm({ ...leadForm, phone: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Ghi chú thời gian muốn xem</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: Thứ 7 tuần này lúc 9h sáng..."
                    value={leadForm.note}
                    onChange={(e) => setLeadForm({ ...leadForm, note: e.target.value })}
                  />
                </div>
                <button type="submit" className="btn-book" style={{ marginTop: "10px", padding: "10px" }}>
                  Xác nhận gửi thông tin
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
