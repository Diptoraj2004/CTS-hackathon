import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  UploadCloud,
  FileText,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Eye,
  Download,
  MoreHorizontal,
  ChevronLeft,
  ChevronRight,
  X,
  FileSpreadsheet,
  FileType2,
} from "lucide-react";
import { AdminLayout } from "../../layouts/AdminLayout";
import {
  DOCUMENTS,
  DOC_SOURCES,
  DOC_DRUGS,
  DOC_FILETYPES,
  DOC_STATUSES,
  type DocStatus,
  type FileType,
} from "../../data/adminData";

const PAGE_SIZE = 10;

// ── File type icon ─────────────────────────────────────────────────────────────
const FileIcon: React.FC<{ type: FileType }> = ({ type }) => {
  if (type === "XLSX") return <FileSpreadsheet size={15} className="dl-file-icon dl-file-icon--xlsx" />;
  if (type === "DOCX") return <FileType2 size={15} className="dl-file-icon dl-file-icon--docx" />;
  return <FileText size={15} className="dl-file-icon dl-file-icon--pdf" />;
};

// ── Status badge ───────────────────────────────────────────────────────────────
const StatusBadge: React.FC<{ status: DocStatus }> = ({ status }) => (
  <span className={`admin-status-badge admin-status-badge--${status.toLowerCase()}`}>
    {status}
  </span>
);

// ── Pagination ─────────────────────────────────────────────────────────────────
interface PaginationProps {
  total: number;
  page: number;
  pageSize: number;
  onChange: (p: number) => void;
}

const Pagination: React.FC<PaginationProps> = ({ total, page, pageSize, onChange }) => {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  // Build page window: always show first/last + up to 3 around current
  const pages: (number | "…")[] = [];
  const range = (from: number, to: number) =>
    Array.from({ length: to - from + 1 }, (_, i) => from + i);

  if (totalPages <= 7) {
    pages.push(...range(1, totalPages));
  } else {
    pages.push(...range(1, Math.min(2, totalPages)));
    if (page > 4) pages.push("…");
    const mid = range(Math.max(3, page - 1), Math.min(totalPages - 2, page + 1));
    pages.push(...mid);
    if (page < totalPages - 3) pages.push("…");
    pages.push(...range(Math.max(totalPages - 1, 3), totalPages));
  }

  return (
    <div className="dl-pagination">
      <span className="dl-pagination-info">
        Showing {Math.min((page - 1) * pageSize + 1, total)}–{Math.min(page * pageSize, total)} of {total} documents
      </span>
      <div className="dl-pagination-controls">
        <button
          className="dl-page-btn"
          disabled={page === 1}
          onClick={() => onChange(page - 1)}
          aria-label="Previous page"
        >
          <ChevronLeft size={14} />
        </button>

        {pages.map((p, i) =>
          p === "…" ? (
            <span key={`ellipsis-${i}`} className="dl-page-ellipsis">…</span>
          ) : (
            <button
              key={p}
              className={`dl-page-btn dl-page-btn--num${p === page ? " dl-page-btn--active" : ""}`}
              onClick={() => onChange(p as number)}
              aria-current={p === page ? "page" : undefined}
            >
              {p}
            </button>
          )
        )}

        <button
          className="dl-page-btn"
          disabled={page === totalPages}
          onClick={() => onChange(page + 1)}
          aria-label="Next page"
        >
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
};

// ── Select dropdown ────────────────────────────────────────────────────────────
interface FilterSelectProps {
  id: string;
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}

const FilterSelect: React.FC<FilterSelectProps> = ({ id, label, value, options, onChange }) => (
  <div className="dl-filter-group">
    <label className="dl-filter-label" htmlFor={id}>{label}</label>
    <select id={id} className="dl-filter-select" value={value} onChange={e => onChange(e.target.value)}>
      <option value="">All {label}s</option>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  </div>
);

// ── Document Library Page ──────────────────────────────────────────────────────
export const DocumentLibrary: React.FC = () => {
  const navigate = useNavigate();

  // Filter state
  const [search, setSearch]           = useState("");
  const [filterSource, setSource]     = useState("");
  const [filterDrug, setDrug]         = useState("");
  const [filterType, setType]         = useState<FileType | "">("");
  const [filterStatus, setStatus]     = useState<DocStatus | "">("");
  const [page, setPage]               = useState(1);

  const hasFilters = search || filterSource || filterDrug || filterType || filterStatus;

  const clearFilters = () => {
    setSearch(""); setSource(""); setDrug(""); setType(""); setStatus(""); setPage(1);
  };

  // Filtered & paginated data
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return DOCUMENTS.filter(doc => {
      if (q && !doc.fileName.toLowerCase().includes(q) && !doc.drug.toLowerCase().includes(q) && !doc.source.toLowerCase().includes(q)) return false;
      if (filterSource && doc.source !== filterSource) return false;
      if (filterDrug   && doc.drug   !== filterDrug)   return false;
      if (filterType   && doc.fileType !== filterType) return false;
      if (filterStatus && doc.status  !== filterStatus)return false;
      return true;
    });
  }, [search, filterSource, filterDrug, filterType, filterStatus]);

  // Reset to page 1 when filters change
  const handleSearch   = (v: string)              => { setSearch(v);       setPage(1); };
  const handleSource   = (v: string)              => { setSource(v);       setPage(1); };
  const handleDrug     = (v: string)              => { setDrug(v);         setPage(1); };
  const handleType     = (v: string)              => { setType(v as FileType | "");   setPage(1); };
  const handleStatus   = (v: string)              => { setStatus(v as DocStatus | "");setPage(1); };

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const pageRows   = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // KPI summary (always from full dataset so counts don't change when filtering)
  const total      = DOCUMENTS.length;
  const processed  = DOCUMENTS.filter(d => d.status === "Processed").length;
  const processing = DOCUMENTS.filter(d => d.status === "Processing").length;
  const errors     = DOCUMENTS.filter(d => d.status === "Error").length;

  return (
    <AdminLayout title="Document Library">
      {/* ── Page header row ── */}
      <div className="dl-page-header">
        <p className="dl-page-subtitle">
          Browse, search and manage all uploaded medical and drug-related documents.
        </p>
        <button
          className="dl-upload-btn"
          type="button"
          onClick={() => navigate("/admin/upload")}
        >
          <UploadCloud size={16} />
          Upload Document
        </button>
      </div>

      {/* ── Search + Filters ── */}
      <div className="admin-card dl-filters-card">
        <div className="dl-search-wrap">
          <Search size={15} className="dl-search-icon" />
          <input
            id="dl-search"
            type="text"
            className="dl-search-input"
            placeholder="Search documents, drugs, or keywords…"
            value={search}
            onChange={e => handleSearch(e.target.value)}
            aria-label="Search documents"
          />
          {search && (
            <button className="dl-search-clear" onClick={() => handleSearch("")} aria-label="Clear search">
              <X size={13} />
            </button>
          )}
        </div>

        <div className="dl-filters-row">
          <FilterSelect id="dl-source" label="Source"    value={filterSource} options={DOC_SOURCES}                          onChange={handleSource} />
          <FilterSelect id="dl-drug"   label="Drug"      value={filterDrug}   options={DOC_DRUGS}                            onChange={handleDrug}   />
          <FilterSelect id="dl-type"   label="File Type" value={filterType}   options={DOC_FILETYPES}                        onChange={handleType}   />
          <FilterSelect id="dl-status" label="Status"    value={filterStatus} options={DOC_STATUSES}                         onChange={handleStatus} />

          {hasFilters && (
            <button className="dl-clear-btn" type="button" onClick={clearFilters}>
              <X size={13} />
              Clear Filters
            </button>
          )}
        </div>
      </div>

      {/* ── KPI Summary Cards ── */}
      <div className="admin-kpi-row dl-kpi-row">
        <div className="admin-kpi-card">
          <div className="admin-kpi-icon admin-kpi-icon--blue"><FileText size={20} /></div>
          <div className="admin-kpi-info">
            <div className="admin-kpi-value">{total}</div>
            <div className="admin-kpi-label">Total Documents</div>
          </div>
        </div>
        <div className="admin-kpi-card">
          <div className="admin-kpi-icon admin-kpi-icon--teal"><CheckCircle2 size={20} /></div>
          <div className="admin-kpi-info">
            <div className="admin-kpi-value">{processed}</div>
            <div className="admin-kpi-label">Processed</div>
          </div>
        </div>
        <div className="admin-kpi-card">
          <div className="admin-kpi-icon admin-kpi-icon--orange"><Clock size={20} /></div>
          <div className="admin-kpi-info">
            <div className="admin-kpi-value">{processing}</div>
            <div className="admin-kpi-label">Processing</div>
          </div>
        </div>
        <div className="admin-kpi-card admin-kpi-card--error">
          <div className="admin-kpi-icon admin-kpi-icon--red"><AlertTriangle size={20} /></div>
          <div className="admin-kpi-info">
            <div className="admin-kpi-value admin-kpi-value--error">{errors}</div>
            <div className="admin-kpi-label">Processing Errors</div>
          </div>
        </div>
      </div>

      {/* ── Document Table ── */}
      <div className="admin-card dl-table-card">
        {filtered.length === 0 ? (
          <div className="dl-empty">
            <Search size={30} className="dl-empty-icon" />
            <p className="dl-empty-text">No documents match your current filters.</p>
            <button className="dl-clear-btn" type="button" onClick={clearFilters}>Clear Filters</button>
          </div>
        ) : (
          <>
            <div className="dl-table-wrap">
              <table className="admin-table dl-table" aria-label="Document library">
                <thead>
                  <tr>
                    <th className="dl-th-check">
                      <input type="checkbox" aria-label="Select all" className="dl-checkbox" />
                    </th>
                    <th>File Name</th>
                    <th>Drug / Topic</th>
                    <th>Source <span className="dl-sort-arrow">↕</span></th>
                    <th>File Type <span className="dl-sort-arrow">↕</span></th>
                    <th>Version <span className="dl-sort-arrow">↕</span></th>
                    <th>Uploaded On <span className="dl-sort-arrow">↕</span></th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map(doc => (
                    <tr key={doc.id}>
                      <td className="dl-td-check">
                        <input type="checkbox" aria-label={`Select ${doc.fileName}`} className="dl-checkbox" />
                      </td>
                      <td>
                        <span className="dl-filename">
                          <FileIcon type={doc.fileType} />
                          {doc.fileName}
                        </span>
                      </td>
                      <td className="dl-drug-cell">{doc.drug}</td>
                      <td>{doc.source}</td>
                      <td>
                        <span className={`dl-filetype-badge dl-filetype-badge--${doc.fileType.toLowerCase()}`}>
                          {doc.fileType}
                        </span>
                      </td>
                      <td className="dl-version-cell">{doc.version}</td>
                      <td className="admin-table-date">{doc.uploadedOn}</td>
                      <td><StatusBadge status={doc.status} /></td>
                      <td>
                        <div className="dl-actions-cell">
                          <button className="dl-action-btn" title="View document" aria-label="View">
                            <Eye size={15} />
                          </button>
                          <button className="dl-action-btn" title="Download document" aria-label="Download">
                            <Download size={15} />
                          </button>
                          <button className="dl-action-btn" title="More options" aria-label="More options">
                            <MoreHorizontal size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Pagination
              total={filtered.length}
              page={page}
              pageSize={PAGE_SIZE}
              onChange={setPage}
            />
          </>
        )}
      </div>
    </AdminLayout>
  );
};
