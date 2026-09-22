import React from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Pencil,
  Stethoscope,
  HeartHandshake,
  FileText,
  AlertTriangle,
  MessageCircle,
  ShieldCheck,
  Users,
} from "lucide-react";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { AppLayout } from "../layouts/AppLayout";
import { loadRagSources, RagSource } from "../data/ragService";

export const SourcesEvidence: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const drug = searchParams.get("drug") || "Amoxicillin";
  const mode = (searchParams.get("mode") as "patient" | "professional") || "professional";

  const modeLabel = mode === "professional" ? "Healthcare Professional" : "Patient / Caregiver";
  const modeDesc =
    mode === "professional"
      ? "Detailed, technical information with clinical context."
      : "Clear, plain-language guidance.";
  const ModeIcon = mode === "professional" ? Stethoscope : HeartHandshake;

  // Load real RAG citations saved by ragService after the last query.
  // Returns null if the user navigates here before asking a question.
  const ragSources: RagSource[] | null = loadRagSources(drug, mode);

  // Download/view action — citations from the knowledge base are served by
  // the authenticated document endpoint. Alert if no URL is available.
  const handleDownloadDocument = (src: RagSource) => {
    if (src.url) {
      window.open(src.url, "_blank", "noopener,noreferrer");
    } else {
      alert(`Source reference: ${src.name}`);
    }
  };

  const handleBackToAnswer = () => {
    navigate(`/results?drug=${encodeURIComponent(drug)}&mode=${mode}`);
  };

  return (
    <AppLayout>
      <Header showAvatar={true} />

      <section className="f03-container container">
        {/* ── LEFT COLUMN (EXACT identical to F-03 / F-04 / F-06) ──────────── */}
        <div className="f03-left-col">
          <div className="f02-step-indicator">
            <span className="step-label">STEP 2 OF 2</span>
            <div className="step-bar">
              <span className="step-segment step-active" />
              <span className="step-segment step-active" />
            </div>
          </div>

          <h1 className="f02-heading">
            Ask with<br />confidence.
          </h1>

          <p className="f02-subtext">
            Get clear, evidence-based answers about your medication from trusted medical sources.
          </p>

          <div className="f02-benefits-list">
            <div className="f02-benefit-item">
              <div className="benefit-icon-badge">
                <MessageCircle size={17} />
              </div>
              <div>
                <strong>Reliable information</strong>
                <span>Based on official medical sources.</span>
              </div>
            </div>

            <div className="f02-benefit-item">
              <div className="benefit-icon-badge">
                <ShieldCheck size={17} />
              </div>
              <div>
                <strong>Ask anything</strong>
                <span>Side effects, interactions, dosage and more.</span>
              </div>
            </div>

            <div className="f02-benefit-item">
              <div className="benefit-icon-badge">
                <Users size={17} />
              </div>
              <div>
                <strong>Tailored to your role</strong>
                <span>Answers that match your needs.</span>
              </div>
            </div>
          </div>

          {/* Decorative pill art */}
          <div className="f03-left-art" aria-hidden="true">
            <div className="f03-art-blister">
              <div className="f03-art-pill f03-art-pill-lg f03-art-pill-red" />
              <div className="f03-art-pill f03-art-pill-lg f03-art-pill-teal" />
              <div className="f03-art-pill f03-art-pill-sm f03-art-pill-orange" />
              <div className="f03-art-pill f03-art-pill-sm f03-art-pill-orange" />
              <div className="f03-art-pill f03-art-pill-sm f03-art-pill-orange" />
              <div className="f03-art-circle" />
            </div>
          </div>
        </div>

        {/* ── CENTER COLUMN (SOURCES & EVIDENCE CONTENT) ── */}
        <div className="f03-center-col">
          {/* Top Bar: Selected Medication & Mode */}
          <div className="f03-selection-bar">
            <div className="f03-sel-drug">
              <div className="f03-sel-pill-icon" aria-hidden="true">
                <div className="sel-pill sel-pill-top" />
                <div className="sel-pill sel-pill-bottom" />
              </div>
              <div className="f03-sel-drug-info">
                <span className="f03-sel-label">Selected Medication</span>
                <span className="f03-sel-drug-name">{drug}</span>
                <span className="f03-sel-drug-desc">Broad-spectrum antibiotic</span>
              </div>
            </div>

            <div className="f03-sel-divider" />

            <div className="f03-sel-mode">
              <div className={`f03-sel-mode-icon ${mode === "patient" ? "f03-mode-blush" : "f03-mode-green"}`}>
                <ModeIcon size={18} />
              </div>
              <div className="f03-sel-mode-info">
                <span className="f03-sel-mode-name">{modeLabel}</span>
                <span className="f03-sel-mode-desc">{modeDesc}</span>
              </div>
            </div>

            <button
              className="f03-change-btn"
              onClick={() => navigate("/select")}
              aria-label="Change medication or mode"
            >
              <Pencil size={13} /> Change
            </button>
          </div>

          {/* Main Card: Sources & Evidence */}
          <div className="f03-chat-card f05-main-card">
            {/* Back button link */}
            <button
              type="button"
              className="f06-back-link"
              onClick={handleBackToAnswer}
              style={{ marginBottom: "16px" }}
            >
              <ArrowLeft size={15} /> Back to answer
            </button>

            {/* Page Title & Subtitle */}
            <h1 className="f05-title">Sources &amp; Evidence</h1>
            <p className="f05-subtitle">
              Review the official medical sources used to generate this answer.
            </p>

            {/* List of Source Cards — real RAG citations or empty state */}
            <div className="f05-sources-list">
              {ragSources === null || ragSources.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    padding: "40px 20px",
                    color: "var(--text-muted, #6b7280)",
                  }}
                >
                  <FileText size={32} style={{ marginBottom: "12px", opacity: 0.4 }} />
                  <p style={{ margin: 0, fontWeight: 600, fontSize: "15px" }}>
                    No verified evidence available
                  </p>
                  <p style={{ margin: "8px 0 0", fontSize: "13px" }}>
                    Ask a question about {drug} first to see the citations used in the
                    answer.
                  </p>
                </div>
              ) : (
                ragSources.map((src, index) => (
                  <article key={src.id} className="f05-card">
                    {/* Card Header */}
                    <div className="f05-card-header">
                      <div className="f05-card-header-left">
                        <span className="f05-source-number">{index + 1}</span>
                        <div className="f05-source-meta">
                          <h3 className="f05-source-name">
                            {src.doc ?? src.name}
                          </h3>
                          <span className="f05-source-org">
                            {src.section ? `Section: ${src.section}` : "Ingested Document"}
                          </span>
                        </div>
                      </div>

                      <div className="f05-card-header-right">
                        <span className="f05-badge f05-badge--official">
                          Ingested Document
                        </span>
                        <button
                          type="button"
                          className="f05-download-arrow-btn"
                          onClick={() => handleDownloadDocument(src)}
                          aria-label={`View ${src.name}`}
                          title="View source reference"
                        >
                          <ArrowRight size={16} />
                        </button>
                      </div>
                    </div>

                    {/* Location Row */}
                    <div className="f05-dates-row">
                      {src.page != null && (
                        <span>
                          Page: <strong>{src.page}</strong>
                        </span>
                      )}
                      {src.page != null && src.chunk_id && (
                        <span className="f05-dates-sep">|</span>
                      )}
                      {src.chunk_id && (
                        <span>
                          Chunk: <strong>{src.chunk_id}</strong>
                        </span>
                      )}
                      {src.page == null && !src.chunk_id && (
                        <span style={{ color: "var(--text-muted, #9ca3af)" }}>
                          No page/chunk reference
                        </span>
                      )}
                    </div>

                    {/* Citation excerpt: show section as context, no fabricated text */}
                    <div className="f05-excerpt-box">
                      <span className="f05-quote-mark">“</span>
                      <p className="f05-excerpt-text">
                        {src.section
                          ? `Retrieved from the “${src.section}” section of this document.`
                          : "Retrieved from the knowledge base."}
                      </p>
                    </div>

                    {/* Card Footer */}
                    <div className="f05-card-footer">
                      <button
                        type="button"
                        className="f05-view-source-btn"
                        onClick={() => handleDownloadDocument(src)}
                      >
                        <span>View source</span>
                        <ArrowRight size={13} />
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
        </div>

        {/* ── RIGHT COLUMN (SIDEBAR CARDS) ── */}
        <div className="f03-right-col">
          {/* Card 1: About Drug */}
          <div className="f03-info-card">
            <div className="f03-info-card-header">
              <FileText size={16} className="f03-info-card-icon" />
              <h4 className="f03-info-card-title">About {drug}</h4>
            </div>
            <p className="f03-info-card-sub">Quick facts from official sources.</p>

            <div className="f03-facts-table">
              <div className="f03-fact-row">
                <span className="f03-fact-label">Drug class</span>
                <span className="f03-fact-value">No verified information available in the current knowledge base.</span>
              </div>
              <div className="f03-fact-row">
                <span className="f03-fact-label">Available as</span>
                <span className="f03-fact-value">No verified information available in the current knowledge base.</span>
              </div>
              <div className="f03-fact-row">
                <span className="f03-fact-label">Common brands</span>
                <span className="f03-fact-value">No verified information available in the current knowledge base.</span>
              </div>
            </div>

            <button className="f03-info-link" type="button">
              View full drug information <ArrowRight size={13} />
            </button>
          </div>

          {/* Card 2: Sources */}
          <div className="f03-info-card f04-sources-card">
            <div className="f03-info-card-header">
              <FileText size={16} className="f03-info-card-icon" />
              <h4 className="f03-info-card-title">Sources</h4>
            </div>
            <p className="f03-info-card-sub">Information from trusted medical sources.</p>

            <div className="f04-sources-list">
              {ragSources && ragSources.length > 0 ? (
                ragSources.map((src, idx) => (
                  <div key={src.id} className="f04-source-item">
                    <span className="f04-source-number">{idx + 1}</span>
                    <div className="f04-source-details">
                      <strong className="f04-source-name">{src.doc ?? src.name}</strong>
                      <button
                        className="f04-source-link"
                        type="button"
                        onClick={() => handleDownloadDocument(src)}
                      >
                        Access data <ArrowRight size={12} />
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p style={{ fontSize: "13px", color: "var(--text-muted, #9ca3af)", margin: 0 }}>
                  No citations yet — ask a question first.
                </p>
              )}
            </div>

            <button
              className="f03-info-link"
              type="button"
              style={{ marginTop: "12px" }}
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            >
              View all sources <ArrowRight size={13} />
            </button>
          </div>

          {/* Card 3: Important Notice */}
          <div className="f03-info-card f03-info-card--tinted">
            <div className="f03-info-card-header">
              <AlertTriangle size={18} className="f03-warning-icon" />
              <h4 className="f03-info-card-title" style={{ color: "#8f3a28" }}>
                Important
              </h4>
            </div>
            <p className="f03-info-card-body" style={{ color: "#6b433b", margin: "8px 0 12px" }}>
              This tool provides information from official medical sources and is not a substitute for
              professional medical advice.
            </p>
            <button className="f03-info-link" type="button" style={{ color: "#8f3a28" }}>
              Learn more <ArrowRight size={13} />
            </button>
          </div>
        </div>
      </section>

      <Footer />
    </AppLayout>
  );
};
