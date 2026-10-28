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
  Trash2
} from "lucide-react";

const INITIAL_GREETING = {
  sender: "bot",
  text: "Xin chào anh/chị! Em là trợ lý tư vấn Bất động sản tại Đà Nẵng. Anh/chị đang có nhu cầu thuê hay mua nhà/căn hộ tại khu vực nào (Hải Châu, Sơn Trà, Ngũ Hành Sơn...) ạ?",
  properties: []
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
    // Mặc định tự động tạo 1 thread mới khi lần đầu vào trang
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

  // Đảm bảo activeThreadId luôn hợp lệ với danh sách threads
  useEffect(() => {
    if (!threads.some((t) => t.id === activeThreadId)) {
      if (threads.length > 0) {
        setActiveThreadId(threads[0].id);
      } else {
        const newThread = createNewThreadObject();
        setThreads([newThread]);
        setActiveThreadId(newThread.id);
      }
    }
  }, [threads, activeThreadId]);

  // Lưu threads vào localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(threads));
    } catch (e) {
      console.error("Lỗi lưu threads:", e);
    }
  }, [threads]);

  // Lưu activeThreadId vào localStorage
  useEffect(() => {
    if (activeThreadId) {
      try {
        localStorage.setItem(ACTIVE_THREAD_KEY, activeThreadId);
      } catch (e) {
        console.error(e);
      }
    }
  }, [activeThreadId]);

  const activeThread = threads.find((t) => t.id === activeThreadId) || threads[0];
  const messages = activeThread?.messages || [];

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [leadForm, setLeadForm] = useState({ name: "", phone: "", note: "" });
  const [leadSuccess, setLeadSuccess] = useState(false);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Tạo thread mới
  const handleCreateNewThread = () => {
    const newThread = createNewThreadObject();
    setThreads((prev) => [newThread, ...prev]);
    setActiveThreadId(newThread.id);
    setInput("");
  };

  // Xóa thread
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

  // Cập nhật messages cho thread đang chọn
  const updateActiveThreadMessages = (updateFn) => {
    setThreads((prev) =>
      prev.map((t) => {
        if (t.id !== activeThreadId) return t;
        const updatedMsgs = typeof updateFn === "function" ? updateFn(t.messages) : updateFn;
        
        // Cập nhật tiêu đề thread từ tin nhắn đầu tiên của user nếu tiêu đề còn là mặc định
        let title = t.title;
        if (t.title === "Cuộc trò chuyện mới") {
          const firstUserMsg = updatedMsgs.find((m) => m.sender === "user");
          if (firstUserMsg) {
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

    const userMsg = { sender: "user", text: query, properties: [] };
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
      let botMsg = { sender: "bot", text: "", properties: [] };

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
          properties: []
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

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="brand-header">
          <div className="brand-badge">
            <Building2 size={24} />
          </div>
          <div>
            <div className="brand-title">Đà Nẵng BĐS AI</div>
            <div className="brand-subtitle">Tư vấn mua bán & Cho thuê</div>
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
                onClick={() => setActiveThreadId(t.id)}
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

        {/* Gợi ý tìm nhanh */}
        <div className="quick-prompts">
          <h4>Gợi ý tìm nhanh</h4>
          <button
            className="prompt-btn"
            onClick={() => handleSend("Tìm thuê căn hộ 2 phòng ngủ Sơn Trà view sông Hàn")}
          >
            🏢 Căn hộ 2PN Sơn Trà view sông Hàn
          </button>
          <button
            className="prompt-btn"
            onClick={() => handleSend("Cần thuê studio phố Tây An Thượng sát biển Mỹ Khê dưới 10 triệu")}
          >
            🌊 Studio sát biển Mỹ Khê dưới 10tr
          </button>
          <button
            className="prompt-btn"
            onClick={() => handleSend("Tìm đất nền Hòa Xuân có sổ đỏ chính chủ")}
          >
            🏡 Đất nền Nam Hòa Xuân sổ đỏ
          </button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="chat-main">
        <div className="chat-header">
          <div>
            <h3 style={{ fontSize: "16px", fontWeight: "700" }}>
              {activeThread?.title || "Trợ lý AI Nhà Đất Đà Nẵng"}
            </h3>
            <p style={{ fontSize: "12px", color: "#64748b" }}>
              ID phiên: <code style={{ background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px" }}>{activeThreadId}</code>
            </p>
          </div>
          <div className="status-badge">
            <div className="status-dot"></div> Sẵn sàng tư vấn
          </div>
        </div>

        <div className="message-list">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message-row ${msg.sender}`}>
              <div className={`avatar ${msg.sender}`}>
                {msg.sender === "bot" ? <Building2 size={18} /> : "Bạn"}
              </div>
              <div className="message-content">
                <div className="bubble">{msg.text}</div>

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
              placeholder="Nhập yêu cầu: Ví dụ tìm thuê nhà Hải Châu dưới 15 triệu, mua đất Hòa Xuân..."
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
