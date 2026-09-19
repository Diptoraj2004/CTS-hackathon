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

  // ── File state ──
  const [file, setFile]           = useState<File | null>(null);
  const [isDragging, setDragging] = useState(false);

  // ── Pipeline state ──
  // stageStatuses: maps stageId → status
  const initStatuses = (): Record<string, StageStatus> =>
    Object.fromEntries(PIPELINE_STAGES.map(s => [s.id, "pending"]));

  const [stageStatuses, setStageStatuses] = useState<Record<string, StageStatus>>(initStatuses);
  const [isProcessing, setIsProcessing]   = useState(false);
  const [isDone, setIsDone]               = useState(false);
  const [hasFailed, setHasFailed]         = useState(false);
  const [revealedDetails, setDetails]     = useState<number>(0); // how many DETAIL_STEPS are revealed
  const [currentDetailProcessing, setCurrentDetailProcessing] = useState<number | null>(null);

  // ── Drag / drop handlers ──
  const handleDragOver  = useCallback((e: React.DragEvent) => { e.preventDefault(); setDragging(true);  }, []);
  const handleDragLeave = useCallback(() => setDragging(false), []);
  const handleDrop      = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) selectFile(dropped);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const selectFile = (f: File) => {
    setFile(f);
    setStageStatuses(initStatuses());
    setIsProcessing(false);
    setIsDone(false);
    setHasFailed(false);
    setDetails(0);
    setCurrentDetailProcessing(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) selectFile(f);
    // reset input so same file can be re-selected
    e.target.value = "";
  };

  const handleRemove = () => {
    setFile(null);
    setStageStatuses(initStatuses());
    setIsProcessing(false);
    setIsDone(false);
    setHasFailed(false);
    setDetails(0);
    setCurrentDetailProcessing(null);
  };

  // ── Simulated upload ──
  const handleUpload = async () => {
    if (!file || isProcessing) return;
    setIsProcessing(true);
    setIsDone(false);
    setHasFailed(false);
    setDetails(0);
    setCurrentDetailProcessing(null);
    setStageStatuses(initStatuses());

    // Progress through each stage sequentially
    let detailIdx = 0;
    for (let i = 0; i < PIPELINE_STAGES.length; i++) {
      const stageId = PIPELINE_STAGES[i].id;

      // Mark current stage as processing
      setStageStatuses(prev => ({ ...prev, [stageId]: "processing" }));

      // Show a "processing" detail bullet if there's a corresponding one
      if (detailIdx < DETAIL_STEPS.length && !DETAIL_STEPS[detailIdx].done) {
        setCurrentDetailProcessing(detailIdx);
      }

      await delay(STAGE_DURATIONS_MS[i]);

      // Mark complete
      setStageStatuses(prev => ({ ...prev, [stageId]: "complete" }));

      // Reveal a detail line on stage complete
      if (detailIdx < DETAIL_STEPS.length) {
        // Some stages emit 2 detail lines (parse → OCR + text extracted)
        const detailsForStage = i === 3 ? 2 : 1;
        for (let d = 0; d < detailsForStage; d++) {
          if (detailIdx < DETAIL_STEPS.length) {
            setDetails(prev => prev + 1);
            setCurrentDetailProcessing(null);
            detailIdx++;
          }
        }
      }
    }

    setIsProcessing(false);
    setIsDone(true);
  };

  const canUpload = !!file && !isProcessing && !isDone;

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

      {/* ── Top row: Drop zone + Selected file ── */}
      <div className="up-top-row">

        {/* Drop zone */}
        <div
          className={`up-dropzone${isDragging ? " up-dropzone--drag" : ""}${file ? " up-dropzone--has-file" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !file && fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Upload document drop zone"
          onKeyDown={e => e.key === "Enter" && !file && fileInputRef.current?.click()}
        >
          <UploadCloud size={44} className="up-dz-icon" />
          <p className="up-dz-heading">Drag &amp; drop your document here</p>
          <p className="up-dz-or">or</p>
          <button
            type="button"
            className="up-choose-btn"
            onClick={e => { e.stopPropagation(); fileInputRef.current?.click(); }}
          >
            Choose File
          </button>
          <p className="up-dz-hint">Supported: PDF / XML / image-based documents</p>
          <p className="up-dz-hint up-dz-hint--small">Maximum file size: 50 MB</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.xml,.png,.jpg,.jpeg,.tiff,.webp,.docx"
            className="up-file-input"
            onChange={handleFileChange}
            aria-label="Choose file"
          />
        </div>

        {/* Selected file card */}
        <div className="admin-card up-file-card">
          <div className="up-file-card-header">
            <Layers size={15} className="up-file-card-icon" />
            <span className="up-file-card-title">Selected File</span>
          </div>

          {file ? (
            <>
              <div className="up-file-info">
                <div className="up-file-thumb">
                  <FileText size={22} className="up-file-thumb-icon" />
                </div>
                <div className="up-file-meta">
                  <span className="up-file-name">{file.name}</span>
                  <span className="up-file-detail">
                    {file.name.split(".").pop()?.toUpperCase() ?? "FILE"}
                    &nbsp;•&nbsp;{formatSize(file.size)}
                    &nbsp;•&nbsp;{isDone ? <span className="up-file-ready">Ready</span> : "Ready to upload"}
                  </span>
                </div>
                <button
                  className="up-file-remove"
                  onClick={handleRemove}
                  aria-label="Remove file"
                  title="Remove file"
                  disabled={isProcessing}
                >
                  <X size={14} />
                </button>
              </div>

              <div className="up-file-actions">
                <button
                  type="button"
                  className="up-change-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isProcessing}
                >
                  <RefreshCw size={13} />
                  Change File
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
                      <><UploadCloud size={14} /> Upload Document</>
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
              <p className="up-file-empty-text">No file selected</p>
              <p className="up-file-empty-sub">Choose or drag a file to begin.</p>
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
            <p className="admin-card-sub">Your document will go through several steps to be validated, processed and indexed.</p>
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

          {revealedDetails === 0 && !isProcessing ? (
            <div className="up-details-empty">
              <Info size={18} className="up-details-empty-icon" />
              <p className="up-details-empty-text">No document uploaded yet.</p>
              <p className="up-details-empty-sub">Upload a document to see processing details here.</p>
            </div>
          ) : (
            <div className="up-details-log">
              {DETAIL_STEPS.slice(0, revealedDetails).map((d, i) => (
                <DetailItem key={i} detail={d} />
              ))}
              {isProcessing && currentDetailProcessing !== null && revealedDetails < DETAIL_STEPS.length && (
                <DetailItem detail={DETAIL_STEPS[currentDetailProcessing]} processing={true} />
              )}
              {isDone && (
                <div className="up-details-done">
                  <CheckCircle2 size={16} className="up-details-done-icon" />
                  <span>Document is ready in the library.</span>
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
            <div className="up-type-item">
              <div className="up-type-icon up-type-icon--img"><Image size={18} /></div>
              <div className="up-type-body">
                <span className="up-type-name">Image-based Documents</span>
                <span className="up-type-desc">Scanned documents, images (OCR will be performed)</span>
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
