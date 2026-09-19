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
import { getSourcesForDrug, EvidenceSource } from "../data/evidenceSources";

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

  const sourcesList: EvidenceSource[] = getSourcesForDrug(drug);

  // Download action wired to placeholder function using documentId
  const handleDownloadDocument = (documentId: string, sourceName: string) => {
    console.log(`[Frontend Placeholder] Downloading document "${sourceName}" (ID: ${documentId})`);
    alert(`Downloading document: ${sourceName} (ID: ${documentId})`);
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

            {/* List of Reusable Source Cards */}
            <div className="f05-sources-list">
              {sourcesList.map((src, index) => (
                <article key={src.documentId} className="f05-card">
                  {/* Card Header */}
                  <div className="f05-card-header">
                    <div className="f05-card-header-left">
                      <span className="f05-source-number">{index + 1}</span>
                      <div className="f05-source-meta">
                        <h3 className="f05-source-name">{src.name}</h3>
                        <span className="f05-source-org">{src.organization}</span>
                      </div>
                    </div>

                    <div className="f05-card-header-right">
                      <span
                        className={`f05-badge ${
                          src.sourceType === "Official Label"
                            ? "f05-badge--official"
                            : "f05-badge--trusted"
                        }`}
                      >
                        {src.sourceType}
                      </span>
                      <button
                        type="button"
                        className="f05-download-arrow-btn"
                        onClick={() => handleDownloadDocument(src.documentId, src.name)}
                        aria-label={`Download ${src.name}`}
                        title="Download document"
                      >
                        <ArrowRight size={16} />
                      </button>
                    </div>
                  </div>

                  {/* Dates Row */}
                  <div className="f05-dates-row">
                    <span>
                      Updated: <strong>{src.updatedAt}</strong>
                    </span>
                    <span className="f05-dates-sep">|</span>
                    <span>
                      Accessed: <strong>{src.accessedAt}</strong>
                    </span>
                  </div>

                  {/* Excerpt Box */}
                  <div className="f05-excerpt-box">
                    <span className="f05-quote-mark">“</span>
                    <p className="f05-excerpt-text">{src.excerpt}</p>
                  </div>

                  {/* Card Footer */}
                  <div className="f05-card-footer">
                    <button
                      type="button"
                      className="f05-view-source-btn"
                      onClick={() => handleDownloadDocument(src.documentId, src.name)}
                    >
                      <span>View source</span>
                      <ArrowRight size={13} />
                    </button>
                  </div>
                </article>
              ))}
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
                <span className="f03-fact-value">Antibiotic (Penicillin)</span>
              </div>
              <div className="f03-fact-row">
                <span className="f03-fact-label">Available as</span>
                <span className="f03-fact-value">Capsule, tablet, syrup, injection</span>
              </div>
              <div className="f03-fact-row">
                <span className="f03-fact-label">Common brands</span>
                <span className="f03-fact-value">Amoxil, Moxatag, Clavamox</span>
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
              {sourcesList.map((src, idx) => (
                <div key={src.documentId} className="f04-source-item">
                  <span className="f04-source-number">{idx + 1}</span>
                  <div className="f04-source-details">
                    <strong className="f04-source-name">{src.name}</strong>
                    <button
                      className="f04-source-link"
                      type="button"
                      onClick={() => handleDownloadDocument(src.documentId, src.name)}
                    >
                      Access data <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              ))}
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
