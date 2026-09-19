import React, { useState, useRef, useCallback, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  UploadCloud,
  FileText,
  X,
  RefreshCw,
  Check,
  AlertCircle,
  Clock,
  ChevronRight,
  Layers,
  Search,
  FileCode2,
  Image,
  Info,
  Loader2,
  FileScan,
  Database,
  CheckCircle2,
  ArrowRight,
} from "lucide-react";
import { AdminLayout } from "../../layouts/AdminLayout";
const API_BASE =
  import.meta.env.VITE_API_BASE || "http://localhost:8000";
// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
type StageStatus = "pending" | "processing" | "complete" | "failed";

interface PipelineStage {
  id: string;
  label: string;
  step: number;
  icon: React.ReactNode;
}

interface ProcessingDetail {
  text: string;
  done: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Pipeline stage definitions (static, UI-only)
// ─────────────────────────────────────────────────────────────────────────────
const PIPELINE_STAGES: PipelineStage[] = [
  { id: "upload",   step: 1, label: "Upload",     icon: <UploadCloud size={20} /> },
  { id: "validate", step: 2, label: "Validate",   icon: <Check       size={20} /> },
  { id: "detect",   step: 3, label: "Detect",     icon: <Search      size={20} /> },
  { id: "parse",    step: 4, label: "Parse / OCR",icon: <FileScan    size={20} /> },
  { id: "index",    step: 5, label: "Index",      icon: <Database    size={20} /> },
  { id: "ready",    step: 6, label: "Ready",      icon: <CheckCircle2 size={20}/> },
];

// Details messages emitted as each stage completes
const DETAIL_STEPS: ProcessingDetail[] = [
  { text: "File uploaded successfully",  done: true  },
  { text: "File validated (no corruption detected)", done: true  },
  { text: "Format detected: PDF document",  done: true  },
  { text: "OCR performed on scanned pages", done: true  },
  { text: "Text extracted successfully",    done: true  },
  { text: "Indexing…",                      done: false },
  { text: "Document indexed and ready",     done: true  },
];

// Stage durations in ms (purely cosmetic simulation)
const STAGE_DURATIONS_MS = [800, 700, 600, 1200, 900, 500];

// Helper to format bytes
const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

// Pipeline stage icon circle
const StageIcon: React.FC<{ stage: PipelineStage; status: StageStatus; isLast: boolean }> = ({
  stage, status, isLast,
}) => {
  const cls = `up-stage-icon up-stage-icon--${status}`;
  return (
    <div className="up-stage-wrap">
      <div className={cls}>
        {status === "processing" ? <Loader2 size={18} className="up-spin" /> : stage.icon}
      </div>
      <span className="up-stage-label">{stage.step}. {stage.label}</span>
      <span className={`up-stage-status up-stage-status--${status}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
      {!isLast && <div className={`up-stage-line up-stage-line--${status === "complete" ? "done" : "idle"}`} />}
    </div>
  );
};

// Processing detail log item
const DetailItem: React.FC<{ detail: ProcessingDetail; processing?: boolean }> = ({ detail, processing }) => (
  <div className={`up-detail-item${processing ? " up-detail-item--processing" : ""}`}>
    {detail.done
      ? <Check size={13} className="up-detail-check" />
      : processing
        ? <Loader2 size={13} className="up-spin up-detail-spin" />
        : <Clock size={13} className="up-detail-clock" />
    }
    <span>{detail.text}</span>
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────
export const UploadProcessing: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Multi-file & Form state ──
  const [files, setFiles]                 = useState<File[]>([]);
  const [drugName, setDrugName]           = useState<string>("");
  const [currentFileIndex, setCurrentFileIndex] = useState<number | null>(null);
  const [completedFileIndices, setCompletedFileIndices] = useState<number[]>([]);
  const [isDragging, setDragging]         = useState(false);

  // ── Pipeline state ──
  const initStatuses = (): Record<string, StageStatus> =>
    Object.fromEntries(PIPELINE_STAGES.map(s => [s.id, "pending"]));

  const [stageStatuses, setStageStatuses] = useState<Record<string, StageStatus>>(initStatuses);
  const [isProcessing, setIsProcessing]   = useState(false);
  const [isDone, setIsDone]               = useState(false);
  const [hasFailed, setHasFailed]         = useState(false);
  const [revealedDetails, setDetails]     = useState<number>(0); // how many DETAIL_STEPS are revealed
  const [currentDetailProcessing, setCurrentDetailProcessing] = useState<number | null>(null);
  const [detailLogs, setDetailLogs]       = useState<ProcessingDetail[]>([]);

  // ── File addition & management ──
  const addFiles = (newFiles: File[]) => {
    if (newFiles.length === 0) return;
    setFiles(prev => [...prev, ...newFiles]);
    setStageStatuses(initStatuses());
    setIsProcessing(false);
    setIsDone(false);
    setHasFailed(false);
    setDetails(0);
    setCurrentDetailProcessing(null);
    setCompletedFileIndices([]);
    setCurrentFileIndex(null);
    setDetailLogs([]);
  };

  // ── Drag / drop handlers ──
  const handleDragOver  = useCallback((e: React.DragEvent) => { e.preventDefault(); setDragging(true);  }, []);
  const handleDragLeave = useCallback(() => setDragging(false), []);
  const handleDrop      = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length > 0) addFiles(dropped);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    if (selected.length > 0) addFiles(selected);
    e.target.value = "";
  };

  const handleRemoveFile = (indexToRemove: number) => {
    setFiles(prev => prev.filter((_, idx) => idx !== indexToRemove));
    if (files.length <= 1) {
      setStageStatuses(initStatuses());
      setIsProcessing(false);
      setIsDone(false);
      setHasFailed(false);
      setDetails(0);
      setCurrentDetailProcessing(null);
      setCompletedFileIndices([]);
      setCurrentFileIndex(null);
      setDetailLogs([]);
    }
  };

  const handleRemoveAll = () => {
    setFiles([]);
    setStageStatuses(initStatuses());
    setIsProcessing(false);
    setIsDone(false);
    setHasFailed(false);
    setDetails(0);
    setCurrentDetailProcessing(null);
    setCompletedFileIndices([]);
    setCurrentFileIndex(null);
    setDetailLogs([]);
  };

  // ── Real upload ingestion pipeline ──
  const handleUpload = async () => {
    if (files.length === 0 || !drugName.trim() || isProcessing) return;
    setIsProcessing(true);
    setIsDone(false);
    setHasFailed(false);
    setDetails(0);
    setCurrentDetailProcessing(null);
    setStageStatuses(initStatuses());
    setCompletedFileIndices([]);
    setDetailLogs([]);

    const cleanDrugName = drugName.trim();

    for (let fIdx = 0; fIdx < files.length; fIdx++) {
      setCurrentFileIndex(fIdx);
      const activeFile = files[fIdx];
      const isMulti = files.length > 1;
      const filePrefix = isMulti ? `[${fIdx + 1}/${files.length} - ${activeFile.name}] ` : "";

      setStageStatuses(initStatuses());

      // Stage 1: Uploading
      setStageStatuses(prev => ({ ...prev, upload: "processing" }));
      setDetailLogs(prev => [
        ...prev,
        { text: `${filePrefix}Uploading document...`, done: false }
      ]);

      try {
        const formData = new FormData();
        formData.append("file", activeFile);

        setStageStatuses(prev => ({ ...prev, upload: "complete", validate: "processing", detect: "processing", parse: "processing" }));

        const url = `${API_BASE}/ingest?drug_name=${encodeURIComponent(cleanDrugName)}`;
        const response = await fetch(url, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          let errorMsg = `Server returned status ${response.status}`;
          try {
            const errData = await response.json();
            if (errData && errData.detail) {
              errorMsg = typeof errData.detail === "string" ? errData.detail : JSON.stringify(errData.detail);
            }
          } catch {
            // fallback to default errorMsg
          }
          throw new Error(errorMsg);
        }

        const result = await response.json();
        const chunksStored = result.chunks_stored ?? 0;

        setStageStatuses(prev => ({
          ...prev,
          validate: "complete",
          detect: "complete",
          parse: "complete",
          index: "complete",
          ready: "complete"
        }));

        setDetailLogs(prev => [
          ...prev.slice(0, -1),
          { text: `${filePrefix}Uploaded successfully`, done: true },
          { text: `${filePrefix}Document parsed and checked for safety`, done: true },
          { text: `${filePrefix}Stored ${chunksStored} chunk(s) in RAG store for "${cleanDrugName}"`, done: true },
        ]);
        setDetails(prev => prev + 3);
        setCompletedFileIndices(prev => [...prev, fIdx]);
      } catch (err: any) {
        setHasFailed(true);
        setStageStatuses(prev => ({
          upload: prev.upload === "complete" ? "complete" : "failed",
          validate: "failed",
          detect: "failed",
          parse: "failed",
          index: "failed",
          ready: "failed",
        }));
        setDetailLogs(prev => [
          ...prev.slice(0, -1),
          { text: `${filePrefix}Ingestion failed: ${err.message || "Unknown error"}`, done: false },
        ]);
        setIsProcessing(false);
        setCurrentFileIndex(null);
        return;
      }
    }

    setCurrentFileIndex(null);
    setIsProcessing(false);
    setIsDone(true);
  };

  const canUpload =
    files.length > 0 &&
    drugName.trim().length > 0 &&
    !isProcessing &&
    !isDone;

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <AdminLayout title="Upload Documentation">
      {/* ── Breadcrumb ── */}
      <nav className="up-breadcrumb" aria-label="Breadcrumb">
        <NavLink to="/admin" className="up-crumb-link">Dashboard</NavLink>
        <ChevronRight size={13} className="up-crumb-sep" />
        <span className="up-crumb-current">Upload / Processing</span>
      </nav>

      {/* ── Page subtitle ── */}
      <p className="up-subtitle">Add verified drug documentation to the DrugDoc AI knowledge base.</p>

      {/* ── Drug Name Input Card ── */}
      <div className="admin-card" style={{ marginBottom: "20px" }}>
        <label
          htmlFor="drug-name-input"
          style={{
            display: "block",
            fontSize: "14px",
            fontWeight: 600,
            marginBottom: "8px",
            color: "var(--color-text-main, #0f172a)",
          }}
        >
          Drug Name <span style={{ color: "#ef4444" }}>*</span>
        </label>
        <input
          id="drug-name-input"
          type="text"
          value={drugName}
          onChange={e => setDrugName(e.target.value)}
          placeholder="e.g. Paracetamol"
          disabled={isProcessing}
          required
          style={{
            width: "100%",
            padding: "10px 14px",
            fontSize: "14px",
            borderRadius: "6px",
            border: "1px solid var(--color-border, #cbd5e1)",
            backgroundColor: isProcessing ? "var(--color-bg-subtle, #f8fafc)" : "#ffffff",
            color: "var(--color-text-main, #0f172a)",
            outline: "none",
            boxSizing: "border-box",
          }}
        />
      </div>

      {/* ── Top row: Drop zone + Selected files ── */}
      <div className="up-top-row">

        {/* Drop zone */}
        <div
          className={`up-dropzone${isDragging ? " up-dropzone--drag" : ""}${files.length > 0 ? " up-dropzone--has-file" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Upload document drop zone"
          onKeyDown={e => e.key === "Enter" && fileInputRef.current?.click()}
        >
          <UploadCloud size={44} className="up-dz-icon" />
          <p className="up-dz-heading">
            {files.length > 0 ? "Drag & drop more documents here" : "Drag & drop your document(s) here"}
          </p>
          <p className="up-dz-or">or</p>
          <button
            type="button"
            className="up-choose-btn"
            onClick={e => { e.stopPropagation(); fileInputRef.current?.click(); }}
          >
            {files.length > 0 ? "Choose More Files" : "Choose Files"}
          </button>
          <p className="up-dz-hint">Supported: PDF / XML documents</p>
          <p className="up-dz-hint up-dz-hint--small">Maximum file size: 50 MB per file</p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.xml"
            className="up-file-input"
            onChange={handleFileChange}
            aria-label="Choose files"
          />
        </div>

        {/* Selected files card */}
        <div className="admin-card up-file-card">
          <div className="up-file-card-header" style={{ justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Layers size={15} className="up-file-card-icon" />
              <span className="up-file-card-title">
                {files.length > 1 ? `Selected Files (${files.length})` : "Selected File"}
              </span>
            </div>
            {files.length > 0 && !isProcessing && (
              <button
                type="button"
                className="up-remove-all-btn"
                onClick={handleRemoveAll}
                title="Remove all files"
              >
                Remove All
              </button>
            )}
          </div>

          {files.length > 0 ? (
            <>
              <div
                className="up-file-list"
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                  maxHeight: "220px",
                  overflowY: "auto",
                  paddingRight: "2px",
                }}
              >
                {files.map((f, idx) => {
                  const isCurrent = currentFileIndex === idx;
                  const isCompleted = completedFileIndices.includes(idx);

                  let statusText = "Ready to upload";
                  let statusClass = "";
                  if (isCompleted) {
                    statusText = "Ready";
                    statusClass = "up-file-ready";
                  } else if (isCurrent) {
                    statusText = "Processing...";
                    statusClass = "up-file-processing";
                  }

                  return (
                    <div key={`${f.name}-${idx}`} className="up-file-info">
                      <div className="up-file-thumb">
                        <FileText size={22} className="up-file-thumb-icon" />
                      </div>
                      <div className="up-file-meta">
                        <span className="up-file-name">{f.name}</span>
                        <span className="up-file-detail">
                          {f.name.split(".").pop()?.toUpperCase() ?? "FILE"}
                          &nbsp;•&nbsp;{formatSize(f.size)}
                          &nbsp;•&nbsp;<span className={statusClass}>{statusText}</span>
                        </span>
                      </div>
                      <button
                        className="up-file-remove"
                        onClick={() => handleRemoveFile(idx)}
                        aria-label={`Remove ${f.name}`}
                        title="Remove file"
                        disabled={isProcessing}
                      >
                        <X size={14} />
                      </button>
                    </div>
                  );
                })}
              </div>

              <div className="up-file-actions">
                <button
                  type="button"
                  className="up-change-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isProcessing}
                >
                  <RefreshCw size={13} />
                  Add More Files
                </button>
                {!isDone ? (
                  <button
                    type="button"
                    className="up-upload-btn"
                    onClick={handleUpload}
                    disabled={!canUpload}
                  >
                    {isProcessing ? (
                      <><Loader2 size={14} className="up-spin" /> Processing…</>
                    ) : (
                      <><UploadCloud size={14} /> {files.length > 1 ? "Upload Documents" : "Upload Document"}</>
                    )}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="up-upload-btn up-upload-btn--done"
                    onClick={() => navigate("/admin/library")}
                  >
                    <ArrowRight size={14} /> View in Library
                  </button>
                )}
              </div>
            </>
          ) : (
            <div className="up-file-empty">
              <FileText size={28} className="up-file-empty-icon" />
              <p className="up-file-empty-text">No files selected</p>
              <p className="up-file-empty-sub">Choose or drag files to begin.</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Processing Pipeline ── */}
      <div className="admin-card up-pipeline-card">
        <div className="up-pipeline-header">
          <FileScan size={16} className="up-pipeline-header-icon" />
          <div>
            <h2 className="admin-card-title" style={{ marginBottom: 0 }}>Processing Pipeline</h2>
            <p className="admin-card-sub">
              {files.length > 1
                ? "Selected documents will go through each step to be validated, processed and indexed."
                : "Your document will go through several steps to be validated, processed and indexed."}
            </p>
          </div>
        </div>
        <div className="up-pipeline-stages">
          {PIPELINE_STAGES.map((stage, i) => (
            <StageIcon
              key={stage.id}
              stage={stage}
              status={stageStatuses[stage.id]}
              isLast={i === PIPELINE_STAGES.length - 1}
            />
          ))}
        </div>
      </div>

      {/* ── Bottom row: Processing Details + Supported Types ── */}
      <div className="up-bottom-row">

        {/* Processing Details */}
        <div className="admin-card up-details-card">
          <div className="up-details-header">
            <FileText size={15} className="up-pipeline-header-icon" />
            <h2 className="admin-card-title" style={{ marginBottom: 0 }}>Processing Details</h2>
          </div>

          {revealedDetails === 0 && !isProcessing && !hasFailed ? (
            <div className="up-details-empty">
              <Info size={18} className="up-details-empty-icon" />
              <p className="up-details-empty-text">No document uploaded yet.</p>
              <p className="up-details-empty-sub">Upload documents to see processing details here.</p>
            </div>
          ) : (
            <div className="up-details-log">
              {detailLogs.map((d, i) => (
                <DetailItem key={i} detail={d} />
              ))}
              {isProcessing && currentDetailProcessing !== null && (
                <DetailItem
                  detail={
                    files.length > 1 && currentFileIndex !== null
                      ? {
                          ...DETAIL_STEPS[currentDetailProcessing],
                          text: `[${currentFileIndex + 1}/${files.length} - ${files[currentFileIndex].name}] ${DETAIL_STEPS[currentDetailProcessing].text}`,
                        }
                      : DETAIL_STEPS[currentDetailProcessing]
                  }
                  processing={true}
                />
              )}
              {isDone && (
                <div className="up-details-done">
                  <CheckCircle2 size={16} className="up-details-done-icon" />
                  <span>
                    {files.length > 1
                      ? `All ${files.length} documents are ready in the library.`
                      : "Document is ready in the library."}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Supported Document Types */}
        <div className="admin-card up-types-card">
          <div className="up-details-header">
            <Layers size={15} className="up-pipeline-header-icon" />
            <h2 className="admin-card-title" style={{ marginBottom: 0 }}>Supported Document Types</h2>
          </div>

          <div className="up-types-list">
            <div className="up-type-item">
              <div className="up-type-icon up-type-icon--pdf"><FileText size={18} /></div>
              <div className="up-type-body">
                <span className="up-type-name">PDF Documents</span>
                <span className="up-type-desc">Drug labels, product information, clinical guidelines, etc.</span>
              </div>
            </div>
            <div className="up-type-item">
              <div className="up-type-icon up-type-icon--xml"><FileCode2 size={18} /></div>
              <div className="up-type-body">
                <span className="up-type-name">XML Documents</span>
                <span className="up-type-desc">Structured regulatory data (e.g. FDA, EMA, WHO)</span>
              </div>
            </div>
          </div>

          <div className="up-types-notice">
            <Info size={13} className="up-types-notice-icon" />
            <span>All uploaded documents are scanned for safety and validated before processing.</span>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
};

// Tiny async delay helper
const delay = (ms: number) => new Promise<void>(res => setTimeout(res, ms));
