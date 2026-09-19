import React from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ShieldCheck, Settings } from "lucide-react";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { AppLayout } from "../layouts/AppLayout";

export const AdminPlaceholder: React.FC = () => {
  const navigate = useNavigate();

  return (
    <AppLayout>
      <Header showAvatar={true} />

      <section className="container f03-container">
        <button
          className="button button-outline back-btn"
          onClick={() => navigate("/login")}
        >
          <ArrowLeft size={16} /> Back to Login
        </button>

        <div className="f03-card" style={{ maxWidth: "600px", margin: "20px auto" }}>
          <div className="f03-header">
            <span className="step-label" style={{ color: "var(--teal-900)" }}>
              ADMINISTRATION DASHBOARD
            </span>
            <h1 style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Settings size={28} className="icon-notice" /> Admin Control Panel
            </h1>
          </div>

          <div className="f03-body">
            <div className="f03-info-box" style={{ background: "rgba(0, 61, 65, 0.06)", borderColor: "rgba(0, 61, 65, 0.2)" }}>
              <ShieldCheck size={24} style={{ color: "var(--teal-900)", flexShrink: 0 }} />
              <div>
                <h3>Admin Session Authenticated</h3>
                <p>
                  You are signed in as an administrator. Administration functionality (user management, audit logs, drug label sync) placeholder.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <Footer isMinimal={true} />
    </AppLayout>
  );
};
