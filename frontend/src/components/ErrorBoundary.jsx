// frontend/src/components/ErrorBoundary.jsx
import React from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "400px",
          padding: "40px 20px",
          background: "#0f172a",
          borderRadius: "16px",
          margin: "20px auto",
          maxWidth: "700px",
          color: "#f8fafc",
          textAlign: "center",
          border: "1px solid rgba(239, 68, 68, 0.3)",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)"
        }}>
          <div style={{
            width: "60px",
            height: "60px",
            borderRadius: "50%",
            background: "rgba(239, 68, 68, 0.15)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: "16px",
            color: "#ef4444"
          }}>
            <AlertTriangle size={32} />
          </div>

          <h3 style={{ fontSize: "1.25rem", fontWeight: "600", marginBottom: "8px" }}>
            {this.props.title || "Đã xảy ra sự cố khi tải giao diện"}
          </h3>

          <p style={{ color: "#94a3b8", fontSize: "0.9rem", maxWidth: "500px", marginBottom: "20px" }}>
            {this.state.error?.message || "Đã xảy ra lỗi không xác định. Vui lòng tải lại trang hoặc nhấn nút bên dưới để khôi phục."}
          </p>

          <button
            onClick={this.handleReset}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 20px",
              background: "#3b82f6",
              color: "#fff",
              border: "none",
              borderRadius: "8px",
              fontWeight: "500",
              cursor: "pointer",
              fontSize: "0.9rem",
              transition: "all 0.2s"
            }}
          >
            <RotateCcw size={16} />
            <span>Thử lại</span>
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
