import React from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle2, ShieldAlert } from "lucide-react";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";

export const ResultsPlaceholder: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const drug = searchParams.get("drug") || "Paracetamol";
  const mode = searchParams.get("mode") || "patient";

  return (
    <main className="landing f03-placeholder-page">
      <Header showAvatar={true} />

      <section className="container f03-container">
        <button
          className="button button-outline back-btn"
          onClick={() => navigate(-1)}
        >
          <ArrowLeft size={16} /> Back
        </button>

        <div className="f03-card">
          <div className="f03-header">
            <span className="step-label">STEP 2 OF 2</span>
            <h1>Drug Documentation Summary</h1>
            <div className="selected-meta-tags">
              <span className="meta-tag drug-tag">Medication: <strong>{drug}</strong></span>
              <span className="meta-tag mode-tag">Mode: <strong>{mode === "patient" ? "Patient / Caregiver" : "Healthcare Professional"}</strong></span>
            </div>
          </div>

          <div className="f03-body">
            <div className="f03-info-box">
              <CheckCircle2 size={24} className="icon-success" />
              <div>
                <h3>RAG Retrieval Complete</h3>
                <p>
                  Official drug label documentation, interactions, side effects, and guidance for <strong>{drug}</strong> have been fetched from trusted medical sources.
                </p>
              </div>
            </div>

            <div className="f03-placeholder-notice">
              <ShieldAlert size={20} className="icon-notice" />
              <span>Step 2 (F03 Results & Evidence View) placeholder screen.</span>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
};
