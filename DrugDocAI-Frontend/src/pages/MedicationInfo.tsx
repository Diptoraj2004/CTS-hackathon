import React, { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Pencil,
  FileText,
  Stethoscope,
  CheckCircle2,
  Package,
  FileCheck,
  AlertTriangle,
  Link as LinkIcon,
  ShieldAlert,
  Info,
  MessageCircle,
  ShieldCheck,
  Users,
} from "lucide-react";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { AppLayout } from "../layouts/AppLayout";
import { getMedicationInfo, MedicationInfoDetails } from "../data/medicationInfoData";
import { loadRagSources, RagSource } from "../data/ragService";

export const MedicationInfo: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const drug = searchParams.get("drug") || "Amoxicillin";
  const mode = (searchParams.get("mode") as "patient" | "professional") || "professional";

  const medInfo: MedicationInfoDetails | null = getMedicationInfo(drug);
  const ragSources: RagSource[] | null = loadRagSources(drug, mode);

  const [activeTab, setActiveTab] = useState<string>("overview");

  const scrollToSection = (sectionId: string) => {
    setActiveTab(sectionId);
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const handleBackToResults = () => {
    navigate(`/results?drug=${encodeURIComponent(drug)}&mode=${mode}`);
  };

  const handleViewSources = () => {
    navigate(`/sources?drug=${encodeURIComponent(drug)}&mode=${mode}`);
  };

  const displaySources = (ragSources || []).map((src, i) => ({
    id: src.id || i + 1,
    name: src.name || src.doc || "Knowledge Base Source",
  }));

  return (
    <AppLayout>
      <Header showAvatar={true} />

      <section className="f03-container container">
        {/* ── LEFT COLUMN (EXACT identical to F-03 / F-04 / F-06 / F-05) ──── */}
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

        {/* ── CENTER COLUMN (MEDICATION INFO CONTENT) ── */}
        <div className="f03-center-col">
          {/* Back button link */}
          <button
            type="button"
            className="f06-back-link"
            onClick={handleBackToResults}
            style={{ marginBottom: "14px" }}
          >
            <ArrowLeft size={15} /> Back to results
          </button>

          {/* Top Bar / Header Box */}
          <div className="mi-header-card">
            <div className="mi-header-left">
              <div className="mi-pill-icon" aria-hidden="true">
                <div className="sel-pill sel-pill-top" />
                <div className="sel-pill sel-pill-bottom" />
              </div>
              <div className="mi-drug-info">
                <span className="mi-label">MEDICATION</span>
                <h1 className="mi-drug-title">{drug}</h1>
                <span className="mi-drug-sub">
                  {medInfo?.description || "No verified information available in the current knowledge base."}
                </span>
              </div>
            </div>

            <div className="mi-header-middle">
              <div className="mi-class-icon-badge">
                <Stethoscope size={18} />
              </div>
              <div className="mi-class-info">
                <span className="mi-class-label">Drug class</span>
                <span className="mi-class-value">
                  {medInfo?.drugClass || "No verified information available in the current knowledge base."}
                </span>
              </div>
            </div>

            <button
              className="f03-change-btn"
              onClick={() => navigate("/select")}
              type="button"
            >
              <Pencil size={13} /> Change Medication
            </button>
          </div>

          {/* Sub-nav Tabs Bar */}
          <nav className="mi-tabs-nav" aria-label="Medication information tabs">
            {[
              { id: "overview", label: "Overview" },
              { id: "uses", label: "Uses" },
              { id: "dosage", label: "Dosage" },
              { id: "side-effects", label: "Side Effects" },
              { id: "interactions", label: "Interactions" },
              { id: "warnings", label: "Warnings" },
              { id: "sources", label: "Sources" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`mi-tab-btn${activeTab === tab.id ? " mi-tab-btn--active" : ""}`}
                onClick={() => scrollToSection(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </nav>

          {/* ── SECTIONS / CARDS STACK ── */}
          <div className="mi-sections-stack">
            {/* 1. Drug Overview */}
            <article id="overview" className="mi-card">
              <div className="mi-card-header">
                <FileText size={18} className="mi-card-icon" />
                <h2 className="mi-card-title">Drug Overview</h2>
              </div>
              <p className="mi-card-body">
                {medInfo?.overview || "No verified information available in the current knowledge base."}
              </p>
            </article>

            {/* 2. Grid: Uses & Available Forms */}
            <div id="uses" className="mi-grid-2col">
              {/* Uses Card */}
              <article className="mi-card">
                <div className="mi-card-header">
                  <CheckCircle2 size={18} className="mi-card-icon" />
                  <h2 className="mi-card-title">Uses</h2>
                </div>
                {medInfo?.uses && medInfo.uses.length > 0 ? (
                  <ul className="mi-bullet-list">
                    {medInfo.uses.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mi-card-body" style={{ color: "var(--text-muted, #6b7280)" }}>
                    No verified information available in the current knowledge base.
                  </p>
                )}
              </article>

              {/* Available Forms Card */}
              <article className="mi-card">
                <div className="mi-card-header">
                  <Package size={18} className="mi-card-icon" />
                  <h2 className="mi-card-title">Available Forms</h2>
                </div>
                {medInfo?.availableForms && medInfo.availableForms.length > 0 ? (
                  <>
                    <ul className="mi-bullet-list">
                      {medInfo.availableForms.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                    {medInfo.formsNote && (
                      <div className="mi-notice-box">
                        <Info size={14} className="mi-notice-icon" />
                        <span>{medInfo.formsNote}</span>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="mi-card-body" style={{ color: "var(--text-muted, #6b7280)" }}>
                    No verified information available in the current knowledge base.
                  </p>
                )}
              </article>
            </div>

            {/* 3. Dosage Information */}
            <article id="dosage" className="mi-card">
              <div className="mi-card-header">
                <FileCheck size={18} className="mi-card-icon" />
                <h2 className="mi-card-title">Dosage Information</h2>
              </div>
              {medInfo?.dosageInformation && medInfo.dosageInformation.length > 0 ? (
                <div className="mi-card-body-stack">
                  {medInfo.dosageInformation.map((paragraph, idx) => (
                    <p key={idx} className="mi-card-body">
                      {paragraph}
                    </p>
                  ))}
                </div>
              ) : (
                <p className="mi-card-body" style={{ color: "var(--text-muted, #6b7280)" }}>
                  No verified information available in the current knowledge base.
                </p>
              )}
            </article>

            {/* 4. Grid: Side Effects & Interactions */}
            <div id="side-effects" className="mi-grid-2col">
              {/* Side Effects Card */}
              <article className="mi-card">
                <div className="mi-card-header">
                  <AlertTriangle size={18} className="mi-card-icon mi-card-icon--orange" />
                  <h2 className="mi-card-title">Common Side Effects</h2>
                </div>
                {medInfo?.commonSideEffects && medInfo.commonSideEffects.length > 0 ? (
                  <>
                    <ul className="mi-bullet-list">
                      {medInfo.commonSideEffects.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                    {medInfo.sideEffectsNote && (
                      <div className="mi-notice-box">
                        <Info size={14} className="mi-notice-icon" />
                        <span>{medInfo.sideEffectsNote}</span>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="mi-card-body" style={{ color: "var(--text-muted, #6b7280)" }}>
                    No verified information available in the current knowledge base.
                  </p>
                )}
              </article>

              {/* Interactions Card */}
              <article id="interactions" className="mi-card">
                <div className="mi-card-header">
                  <LinkIcon size={18} className="mi-card-icon" />
                  <h2 className="mi-card-title">Interactions</h2>
                </div>
                {medInfo?.interactions && medInfo.interactions.length > 0 ? (
                  <>
                    <ul className="mi-bullet-list">
                      {medInfo.interactions.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                    {medInfo.interactionsNote && (
                      <div className="mi-notice-box">
                        <Info size={14} className="mi-notice-icon" />
                        <span>{medInfo.interactionsNote}</span>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="mi-card-body" style={{ color: "var(--text-muted, #6b7280)" }}>
                    No verified information available in the current knowledge base.
                  </p>
                )}
              </article>
            </div>

            {/* 5. Warnings & Precautions */}
            <article id="warnings" className="mi-card">
              <div className="mi-card-header">
                <ShieldAlert size={18} className="mi-card-icon mi-card-icon--teal" />
                <h2 className="mi-card-title">Warnings &amp; Precautions</h2>
              </div>
              {medInfo?.warnings && medInfo.warnings.length > 0 ? (
                <ul className="mi-bullet-list">
                  {medInfo.warnings.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="mi-card-body" style={{ color: "var(--text-muted, #6b7280)" }}>
                  No verified information available in the current knowledge base.
                </p>
              )}
            </article>

            {/* Compact Sources Link Banner */}
            <div id="sources" className="mi-sources-banner">
              <div className="mi-sources-banner-info">
                <FileText size={16} className="mi-sources-banner-icon" />
                <span>
                  {displaySources.length > 0
                    ? `Information retrieved from ${displaySources.length} verified source(s).`
                    : "No verified information available in the current knowledge base."}
                </span>
              </div>
              <button
                type="button"
                className="mi-sources-banner-btn"
                onClick={handleViewSources}
              >
                <span>View Sources &amp; Evidence</span>
                <ArrowRight size={13} />
              </button>
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
                <span className="f03-fact-value">
                  {medInfo?.drugClass || "No verified information available in the current knowledge base."}
                </span>
              </div>
              <div className="f03-fact-row">
                <span className="f03-fact-label">Available as</span>
                <span className="f03-fact-value">
                  {medInfo?.availableForms && medInfo.availableForms.length > 0
                    ? medInfo.availableForms.join(", ")
                    : "No verified information available in the current knowledge base."}
                </span>
              </div>
              <div className="f03-fact-row">
                <span className="f03-fact-label">Common brands</span>
                <span className="f03-fact-value">
                  No verified information available in the current knowledge base.
                </span>
              </div>
            </div>

            <button
              className="f03-info-link"
              type="button"
              onClick={() => scrollToSection("overview")}
            >
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
              {displaySources.length > 0 ? (
                displaySources.map((src) => (
                  <div key={src.id} className="f04-source-item">
                    <span className="f04-source-number">{src.id}</span>
                    <div className="f04-source-details">
                      <strong className="f04-source-name">{src.name}</strong>
                      <button
                        className="f04-source-link"
                        type="button"
                        onClick={handleViewSources}
                      >
                        Access data <ArrowRight size={12} />
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p style={{ fontSize: "13px", color: "var(--text-muted, #9ca3af)", margin: 0 }}>
                  No verified information available in the current knowledge base.
                </p>
              )}
            </div>

            <button
              className="f03-info-link"
              type="button"
              style={{ marginTop: "12px" }}
              onClick={handleViewSources}
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

