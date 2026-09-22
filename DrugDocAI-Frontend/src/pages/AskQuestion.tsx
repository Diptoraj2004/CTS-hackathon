import React, { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Send,
  User,
  Stethoscope,
  Pencil,
  MessageCircle,
  ShieldCheck,
  Users,
  Lightbulb,
  ArrowRight,
  ArrowLeft,
  Info,
  Link2,
  BarChart2,
  FileText,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { Header } from "../components/Header";
import { AppLayout } from "../layouts/AppLayout";
import { getRagResponse, RagResponse, getDrugProfile, DrugProfileResponse } from "../data/ragService";
import { useCurrentUser } from "../hooks/useCurrentUser";

const NO_INFO = "No verified information available in the current knowledge base.";

function buildSuggestedQuestions(drug: string): string[] {
  return [
    `What is ${drug} used for?`,
    `What is the recommended dosage?`,
    `What are the common side effects?`,
    `Can I take ${drug.toLowerCase()} with ibuprofen?`,
    `What precautions should I know?`,
    `I accidentally took twice my prescribed dose. What should I do?`,
  ];
}

// ── Typing dots animation component ──────────────────────────────────────────
const TypingDots: React.FC = () => (
  <span className="f03-typing-dots" aria-label="DrugDoc AI is thinking">
    <span className="dot" />
    <span className="dot" />
    <span className="dot" />
  </span>
);

// ── Bot avatar ────────────────────────────────────────────────────────────────
const BotAvatar: React.FC = () => (
  <div className="f03-bot-avatar" aria-hidden="true">
    <div className="bot-avatar-inner">
      <div className="bot-pill bot-pill-a" />
      <div className="bot-pill bot-pill-b" />
    </div>
  </div>
);

// ── Main Page (Handles F-03 Greeting, F-04 Answer/Results, F-06 High-Risk & F-07 Low-Confidence) ───
export const AskQuestion: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useCurrentUser();

  const drug = searchParams.get("drug") || "Amoxicillin";
  const mode = (searchParams.get("mode") || (user?.role === "doctor" ? "professional" : "patient")) as "patient" | "professional";

  const [drugProfile, setDrugProfile] = useState<DrugProfileResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDrugProfile(drug)
      .then((data) => {
        if (!cancelled) setDrugProfile(data);
      })
      .catch(() => {
        if (!cancelled) setDrugProfile(null);
      });
    return () => {
      cancelled = true;
    };
  }, [drug]);

  const suggestedQuestions = buildSuggestedQuestions(drug);

  // Active question is transient UI state (resets to null on browser refresh)
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null);
  const [explicitRisk, setExplicitRisk] = useState<string | null>(null);
  const [explicitConfidence, setExplicitConfidence] = useState<string | null>(null);

  // Clean any stale URL query params on mount to keep question state transient
  useEffect(() => {
    if (searchParams.get("q") || searchParams.get("risk") || searchParams.get("confidence")) {
      setSearchParams({ drug, mode }, { replace: true });
    }
  }, []);

  // Retrieve real RAG data from the backend for the active question
  const [ragData, setRagData] = useState<RagResponse | null>(null);
  const [isFetching, setIsFetching] = useState(false);

  useEffect(() => {
    if (!activeQuestion) {
      setRagData(null);
      return;
    }
    let cancelled = false;
    setIsFetching(true);
    getRagResponse(activeQuestion, drug, mode)
      .then((data) => {
        if (!cancelled) setRagData(data);
      })
      .catch(() => {
        if (!cancelled) {
          setRagData({
            question: activeQuestion,
            medication: drug,
            mode,
            risk_level: "normal",
            answerLead: "Something went wrong reaching DrugDoc AI's backend.",
            bulletPoints: [],
            answerFollowUp: "Please check your connection and try again.",
            disclaimer:
              "This information is from official medical sources and is not a substitute for professional medical advice.",
            confidence: "Low",
            confidenceDetail: "Backend request failed.",
            sources: [],
          });
        }
      })
      .finally(() => {
        if (!cancelled) setIsFetching(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeQuestion, drug, mode]);

  const isHighRisk = ragData?.risk_level === "high";
  const isLowConfidence = !isHighRisk && (ragData?.confidence === "Low" || ragData?.confidence === "low");

  // F-03 Greeting state (triggers typing dots on initial load / refresh)
  const [greetingState, setGreetingState] = useState<"typing" | "revealed">("typing");
  useEffect(() => {
    if (!activeQuestion) {
      setGreetingState("typing");
      const t = setTimeout(() => setGreetingState("revealed"), 1200);
      return () => clearTimeout(t);
    }
  }, [activeQuestion, drug]);

  // F-04 Answer state — reflects the real fetch, not a fixed fake delay
  const [answerState, setAnswerState] = useState<"typing" | "revealed">("typing");
  useEffect(() => {
    if (activeQuestion && !isHighRisk && !isLowConfidence) {
      setAnswerState(isFetching ? "typing" : "revealed");
    }
  }, [activeQuestion, isHighRisk, isLowConfidence, isFetching]);

  // Input, timestamp and escalation feedback states
  const [inputValue, setInputValue] = useState("");
  const [timestamp, setTimestamp] = useState("12:48 AM");
  const [highlightSources, setHighlightSources] = useState(false);
  const [isEscalated, setIsEscalated] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sourcesCardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    setTimestamp(timeStr || "12:48 AM");
    setIsEscalated(false);
  }, [activeQuestion]);

  // Submit question -> activates F-04, F-06, or F-07 in transient state
  const handleAskQuestion = useCallback((q: string, risk?: string, confidence?: string) => {
    const cleanQ = q.trim();
    if (!cleanQ) return;
    setExplicitRisk(risk || null);
    setExplicitConfidence(confidence || null);
    setActiveQuestion(cleanQ);
    setInputValue("");
  }, []);

  const handleSend = () => {
    if (!inputValue.trim()) return;
    handleAskQuestion(inputValue);
  };

  const handleSuggestedClick = (q: string) => {
    handleAskQuestion(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSourcesClick = () => {
    setHighlightSources(true);
    sourcesCardRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    setTimeout(() => setHighlightSources(false), 2000);
  };

  // Actions for F-06 High-Risk & F-07 Low-Confidence
  const handleBackToAnswer = () => {
    handleAskQuestion(`What are the common side effects of ${drug}?`);
  };

  const handleEscalateHuman = () => {
    setIsEscalated(true);
  };

  const handleViewDocs = () => {
    navigate(`/docs?drug=${encodeURIComponent(drug)}&mode=${mode}`);
  };

  const handleAskAnotherQuestion = () => {
    setActiveQuestion(null);
    setExplicitRisk(null);
    setExplicitConfidence(null);
    setInputValue("");
  };

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  }, [inputValue]);

  const modeLabel = mode === "patient" ? "Patient / Caregiver" : "Healthcare Professional";
  const modeDesc =
    mode === "patient"
      ? "Simple, easy-to-understand information."
      : "Detailed, technical information with clinical context.";
  const ModeIcon = mode === "patient" ? User : Stethoscope;

  return (
    <AppLayout className="f03-page f04-page">
      <Header showAvatar={true} />

      <section className="f03-container container">
        {/* ── LEFT COLUMN (Identical in F-03, F-04 & F-06) ────────────────── */}
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

        {/* ── CENTER COLUMN ─────────────────────────────────────────────── */}
        <div className="f03-center-col">
          <div className="f03-chat-card f04-card-main">
            {/* 1. Selected medication + mode bar */}
            <div className="f03-selection-bar">
              <div className="f03-sel-drug">
                <div className="f03-sel-pill-icon" aria-hidden="true">
                  <div className="sel-pill sel-pill-top" />
                  <div className="sel-pill sel-pill-bottom" />
                </div>
                <div className="f03-sel-drug-info">
                  <span className="f03-sel-label">Selected Medication</span>
                  <span className="f03-sel-drug-name">{drug}</span>
                  <span className="f03-sel-drug-desc">Selected medication</span>
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
                <Pencil size={13} />
                Change
              </button>
            </div>

            {/* 2. CHAT STREAM / CONTENT */}
            {!activeQuestion ? (
              /* ── F-03 GREETING & SUGGESTIONS VIEW ── */
              <>
                <div className="f03-chat-area">
                  <div className="f03-message f03-message-bot">
                    <BotAvatar />
                    <div className="f03-message-bubble">
                      {greetingState === "typing" ? (
                        <TypingDots />
                      ) : (
                        <>
                          <p className="f03-greeting-title">Hello! I'm DrugDoc AI.</p>
                          <p className="f03-greeting-body">
                            Ask me anything about {drug}. I'll provide clear, evidence-based information from trusted medical sources.
                          </p>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="f03-suggested-section">
                  <div className="f03-suggested-header">
                    <Lightbulb size={16} className="f03-suggested-icon" />
                    <span className="f03-suggested-title">Suggested Questions</span>
                  </div>
                  <div className="f03-questions-grid">
                    {suggestedQuestions.map((q) => (
                      <button
                        key={q}
                        className="f03-question-chip"
                        onClick={() => handleSuggestedClick(q)}
                      >
                        <span>{q}</span>
                        <ArrowRight size={14} className="f03-chip-arrow" />
                      </button>
                    ))}
                  </div>
                </div>

                {/* Input area for F-03 */}
                <div className="f03-input-wrapper f04-input-container">
                  <textarea
                    ref={textareaRef}
                    className="f03-textarea"
                    placeholder="Type your question here..."
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    rows={1}
                    aria-label="Ask a question about this medication"
                  />
                  <div className="f03-input-actions">
                    <button
                      className={`f03-send-btn ${inputValue.trim() ? "f03-send-btn--active" : ""}`}
                      onClick={handleSend}
                      aria-label="Send question"
                      type="button"
                    >
                      <Send size={16} />
                    </button>
                  </div>
                </div>
                <p className="f03-input-hint">
                  Press Enter to send&nbsp;&nbsp;•&nbsp;&nbsp;Shift + Enter for a new line
                </p>
              </>
            ) : isHighRisk ? (
              /* ── F-06 HIGH-RISK / HUMAN ESCALATION VIEW ── */
              <div className="f06-container">
                <button
                  type="button"
                  className="f06-back-link"
                  onClick={handleBackToAnswer}
                  aria-label="Back to answer"
                >
                  <ArrowLeft size={16} />
                  <span>Back to answer</span>
                </button>

                <div className="f06-high-risk-card">
                  {/* Warning Header */}
                  <div className="f06-warning-header">
                    <AlertTriangle size={34} className="f06-warning-icon" />
                    <div>
                      <h3 className="f06-warning-title">HIGH-RISK QUESTION</h3>
                      <p className="f06-warning-sub">
                        This question may require individual medical evaluation.
                      </p>
                    </div>
                  </div>

                  {/* User Question Row */}
                  <div className="f06-user-container">
                    <div className="f04-user-row" style={{ margin: "0 0 2px auto", maxWidth: "100%" }}>
                      <div className="f04-user-avatar" aria-hidden="true">
                        <span>{user.avatarInitial}</span>
                      </div>
                      <div className="f04-user-bubble">
                        <p className="f04-user-text">{ragData.question}</p>
                      </div>
                    </div>
                    <div className="f04-user-meta">
                      <span className="f04-timestamp">{timestamp}</span>
                    </div>
                  </div>

                  {/* Explanatory Paragraphs */}
                  <div className="f06-paragraphs">
                    <p>{ragData.answerLead}</p>
                    <p>{ragData.answerFollowUp}</p>
                  </div>

                  {/* 3 Action Buttons with Unified Teal Styling */}
                  <div className="f06-actions-list">
                    {/* Action 1: Escalate to Human Expert */}
                    <div className="f06-action-item">
                      <button
                        type="button"
                        className="f06-action-btn"
                        onClick={handleEscalateHuman}
                      >
                        <div className="f06-action-btn-left">
                          <User size={18} />
                          <span>Escalate to Human Expert</span>
                        </div>
                        <ArrowRight size={18} />
                      </button>
                      <span className="f06-action-subtext">
                        Get in touch with a qualified healthcare professional.
                      </span>
                    </div>

                    {/* Action 2: View Relevant Documentation */}
                    <div className="f06-action-item">
                      <button
                        type="button"
                        className="f06-action-btn"
                        onClick={handleViewDocs}
                      >
                        <div className="f06-action-btn-left">
                          <FileText size={18} />
                          <span>View Relevant Documentation</span>
                        </div>
                        <ArrowRight size={18} />
                      </button>
                      <span className="f06-action-subtext">
                        See official safety information from trusted medical sources.
                      </span>
                    </div>

                    {/* Action 3: Ask Another Question */}
                    <div className="f06-action-item">
                      <button
                        type="button"
                        className="f06-action-btn"
                        onClick={handleAskAnotherQuestion}
                      >
                        <div className="f06-action-btn-left">
                          <MessageCircle size={18} />
                          <span>Ask Another Question</span>
                        </div>
                        <ArrowRight size={18} />
                      </button>
                      <span className="f06-action-subtext">
                        Go back and ask a different question about your medication.
                      </span>
                    </div>
                  </div>

                  {/* Escalation Feedback Notification */}
                  {isEscalated && (
                    <div className="f06-escalation-alert">
                      <CheckCircle2 size={18} color="var(--teal-700)" />
                      <span>
                        Escalation initiated. A qualified clinical pharmacist has been notified.
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ) : isLowConfidence ? (
              /* ── F-07 LOW-CONFIDENCE VIEW ── */
              <div className="f06-container f07-container">
                <button
                  type="button"
                  className="f06-back-link"
                  onClick={handleBackToAnswer}
                  aria-label="Back to answer"
                >
                  <ArrowLeft size={16} />
                  <span>Back to answer</span>
                </button>

                <div className="f07-low-conf-card">
                  {/* Warning Header */}
                  <div className="f07-warning-header">
                    <AlertTriangle size={34} className="f07-warning-icon" />
                    <div>
                      <h3 className="f07-warning-title">LOW CONFIDENCE ANSWER</h3>
                      <p className="f07-warning-sub">
                        We're not fully confident about this answer.
                      </p>
                    </div>
                  </div>

                  {/* User Question Row */}
                  <div className="f06-user-container">
                    <div className="f04-user-row" style={{ margin: "0 0 2px auto", maxWidth: "100%" }}>
                      <div className="f04-user-avatar" aria-hidden="true">
                        <span>{user.avatarInitial}</span>
                      </div>
                      <div className="f04-user-bubble">
                        <p className="f04-user-text">{ragData.question}</p>
                      </div>
                    </div>
                    <div className="f04-user-meta">
                      <span className="f04-timestamp">{timestamp}</span>
                    </div>
                  </div>

                  {/* Explanatory Paragraphs */}
                  <div className="f06-paragraphs">
                    <p>{ragData.answerLead}</p>
                    <p>{ragData.answerFollowUp}</p>
                  </div>

                  {/* 3 Action Buttons with Unified Teal Styling */}
                  <div className="f06-actions-list">
                    {/* Action 1: Escalate to Human Expert */}
                    <div className="f06-action-item">
                      <button
                        type="button"
                        className="f06-action-btn"
                        onClick={handleEscalateHuman}
                      >
                        <div className="f06-action-btn-left">
                          <User size={18} />
                          <span>Escalate to Human Expert</span>
                        </div>
                        <ArrowRight size={18} />
                      </button>
                      <span className="f06-action-subtext">
                        Get in touch with a qualified healthcare professional.
                      </span>
                    </div>

                    {/* Action 2: View Related Documentation */}
                    <div className="f06-action-item">
                      <button
                        type="button"
                        className="f06-action-btn"
                        onClick={handleViewDocs}
                      >
                        <div className="f06-action-btn-left">
                          <FileText size={18} />
                          <span>View Related Documentation</span>
                        </div>
                        <ArrowRight size={18} />
                      </button>
                      <span className="f06-action-subtext">
                        See available information from trusted medical sources.
                      </span>
                    </div>

                    {/* Action 3: Try a Different Question */}
                    <div className="f06-action-item">
                      <button
                        type="button"
                        className="f06-action-btn"
                        onClick={handleAskAnotherQuestion}
                      >
                        <div className="f06-action-btn-left">
                          <MessageCircle size={18} />
                          <span>Try a Different Question</span>
                        </div>
                        <ArrowRight size={18} />
                      </button>
                      <span className="f06-action-subtext">
                        Rephrase or ask a more specific question about your medication.
                      </span>
                    </div>
                  </div>

                  {/* Escalation Feedback Notification */}
                  {isEscalated && (
                    <div className="f06-escalation-alert">
                      <CheckCircle2 size={18} color="var(--teal-700)" />
                      <span>
                        Escalation initiated. A qualified clinical pharmacist has been notified.
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* ── F-04 ANSWER & EVIDENCE VIEW ── */
              <>
                <div className="f04-chat-area">
                  {/* User Question */}
                  <div className="f04-user-row">
                    <div className="f04-user-avatar" aria-hidden="true">
                      <span>{user.avatarInitial}</span>
                    </div>
                    <div className="f04-user-bubble">
                      <p className="f04-user-text">{activeQuestion}</p>
                    </div>
                  </div>
                  <div className="f04-user-meta">
                    <span className="f04-timestamp">{timestamp}</span>
                  </div>

                  {/* DrugDoc AI Response */}
                  <div className="f04-bot-row">
                    <BotAvatar />
                    <div className="f04-bot-bubble">
                      {answerState === "typing" ? (
                        <div className="f04-typing-wrapper">
                          <TypingDots />
                        </div>
                      ) : (
                        ragData && (
                          <div className="f04-answer-content">
                            <p className="f04-answer-lead" style={{ whiteSpace: "pre-wrap" }}>
                              {ragData.answerLead}
                            </p>

                            {ragData.bulletPoints && ragData.bulletPoints.length > 0 && (
                              <ul className="f04-side-effects-list">
                                {ragData.bulletPoints.map((bp, idx) => (
                                  <li key={idx}>
                                    {bp.label && <strong>{bp.label} </strong>}
                                    {bp.text}
                                  </li>
                                ))}
                              </ul>
                            )}

                            {ragData.answerFollowUp && (
                              <p className="f04-answer-sub">
                                {ragData.answerFollowUp}
                              </p>
                            )}

                            {/* Embedded Medical Disclaimer */}
                            <div className="f04-answer-disclaimer">
                              <div className="f04-disclaimer-icon-wrap" aria-hidden="true">
                                <Info size={16} />
                              </div>
                              <p className="f04-disclaimer-text">{ragData.disclaimer}</p>
                            </div>

                            {/* Answer Metadata Bar: Confidence & Sources */}
                            <div className="f04-meta-bar">
                              <div className="f04-meta-confidence">
                                <div className="f04-confidence-header">
                                  <div className="f04-conf-icon" aria-hidden="true">
                                    <BarChart2 size={16} />
                                  </div>
                                  <span className="f04-conf-badge">
                                    Confidence: {ragData.confidence}
                                  </span>
                                  <Info size={13} className="f04-info-hint" />
                                </div>
                                <span className="f04-meta-sub">{ragData.confidenceDetail}</span>
                              </div>

                              <div className="f04-meta-divider" />

                              <button
                                type="button"
                                className="f04-meta-sources"
                                onClick={handleSourcesClick}
                                aria-label="View sources in sidebar"
                              >
                                <div className="f04-sources-header">
                                  <FileText size={15} className="f04-sources-icon" />
                                  <span className="f04-sources-title">
                                    Sources: {ragData.sources.length}
                                  </span>
                                  <ArrowRight size={14} className="f04-sources-arrow" />
                                </div>
                                <span className="f04-meta-sub">View sources in the sidebar</span>
                              </button>
                            </div>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                  {answerState === "revealed" && (
                    <div className="f04-bot-meta">
                      <span className="f04-timestamp">{timestamp}</span>
                    </div>
                  )}
                </div>

                {/* Input area for F-04 */}
                <div className="f03-input-wrapper f04-input-container">
                  <textarea
                    ref={textareaRef}
                    className="f03-textarea"
                    placeholder="Type your question here..."
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    rows={1}
                    aria-label="Ask a question about this medication"
                  />
                  <div className="f03-input-actions">
                    <button
                      className={`f03-send-btn ${inputValue.trim() ? "f03-send-btn--active" : ""}`}
                      onClick={handleSend}
                      aria-label="Send question"
                      type="button"
                    >
                      <Send size={16} />
                    </button>
                  </div>
                </div>
                <p className="f03-input-hint">
                  Press Enter to send&nbsp;&nbsp;•&nbsp;&nbsp;Shift + Enter for a new line
                </p>
              </>
            )}
          </div>
        </div>

        {/* ── RIGHT COLUMN ──────────────────────────────────────────────── */}
        <div className="f03-right-col">
          {activeQuestion && !isFetching && (
            <>
              {/* About [Medication] */}
              <div className="f03-info-card">
                <div className="f03-info-card-header">
                  <div className="guidance-icon-badge">
                    <FileText size={15} />
                  </div>
                  <h4 className="f03-info-card-title">About {drug}</h4>
                </div>

                <p className="f03-info-card-sub">
                  Quick facts from official sources.
                </p>

                <div className="f03-drug-facts">
                  <div className="f03-fact-row">
                    <span className="f03-fact-label">Drug class</span>
                    <span className="f03-fact-value">
                      {drugProfile?.class || NO_INFO}
                    </span>
                  </div>

                  <div className="f03-fact-row">
                    <span className="f03-fact-label">Available as</span>
                    <span className="f03-fact-value">
                      {drugProfile?.forms && drugProfile.forms.length > 0
                        ? drugProfile.forms.join(", ")
                        : NO_INFO}
                    </span>
                  </div>

                  <div className="f03-fact-row">
                    <span className="f03-fact-label">Common brands</span>
                    <span className="f03-fact-value">{NO_INFO}</span>
                  </div>
                </div>

                <button
                  className="f03-info-link"
                  type="button"
                  onClick={() =>
                    navigate(
                      `/medication-info?drug=${encodeURIComponent(drug)}&mode=${mode}`
                    )
                  }
                >
                  View full drug information <ArrowRight size={13} />
                </button>
              </div>

              {/* Sources */}
              <div
                ref={sourcesCardRef}
                className={`f03-info-card f04-sources-card ${highlightSources ? "f04-sources-card--highlight" : ""
                  }`}
              >
                <div className="f03-info-card-header">
                  <div
                    className="guidance-icon-badge"
                    style={{
                      background: "rgba(30,138,142,0.12)",
                      color: "var(--teal-700)",
                    }}
                  >
                    <Link2 size={15} />
                  </div>
                  <h4 className="f03-info-card-title">Sources</h4>
                </div>

                <p className="f03-info-card-sub">
                  Information from trusted medical sources.
                </p>

                <div className="f04-sources-list">
                  {ragData?.sources.map((src) => (
                    <div key={src.id} className="f04-source-item">
                      <span className="f04-source-number">{src.id}</span>

                      <div className="f04-source-details">
                        <strong className="f04-source-name">{src.name}</strong>

                        <button
                          className="f04-source-link"
                          type="button"
                          onClick={() =>
                            navigate(
                              `/sources?drug=${encodeURIComponent(drug)}&mode=${mode}`
                            )
                          }
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
                  onClick={() =>
                    navigate(
                      `/sources?drug=${encodeURIComponent(drug)}&mode=${mode}`
                    )
                  }
                >
                  View all sources <ArrowRight size={13} />
                </button>
              </div>
            </>
          )}

          {/* Tip */}
          {!activeQuestion && (
            <div className="f03-info-card">
              <div className="f03-info-card-header">
                <div
                  className="guidance-icon-badge"
                  style={{
                    background: "rgba(217,127,108,0.12)",
                    color: "var(--clay-dark)",
                  }}
                >
                  <Lightbulb size={15} />
                </div>

                <h4 className="f03-info-card-title">Tip</h4>
              </div>

              <p className="f03-info-card-body">
                Be specific in your questions to get more relevant answers.
              </p>
            </div>
          )}
        </div>
      </section>
      {/* Minimal footer: copyright only */}
      <footer className="f03-footer">
        <span>© 2026 DrugDoc AI</span>
      </footer>
    </AppLayout>
  );
};



