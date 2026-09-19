import React, { useState, useMemo } from "react";
import {
  Download,
  Calendar,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  FileText,
  UploadCloud,
  Database,
  User,
  AlertTriangle,
  Trash2,
  ShieldCheck,
  UserCheck,
  AlertCircle,
  CheckCircle2,
  Info,
} from "lucide-react";
import { AdminLayout } from "../../layouts/AdminLayout";
import {
  AUDIT_LOGS,
  AUDIT_USERS,
  AUDIT_ACTIONS,
  AUDIT_RESOURCES,
  AUDIT_STATUSES,
  AuditLogRecord,
  ActionType,
  AuditStatus,
} from "../../data/adminData";

const ITEMS_PER_PAGE = 10;

// Helper for rendering action-specific icons in the table
const getActionIcon = (action: ActionType) => {
  switch (action) {
    case "Document Processed":
      return <FileText size={16} className="al-action-icon al-action-icon--blue" />;
    case "File Uploaded":
      return <UploadCloud size={16} className="al-action-icon al-action-icon--teal" />;
    case "Document Indexed":
      return <Database size={16} className="al-action-icon al-action-icon--teal" />;
    case "Login":
      return <User size={16} className="al-action-icon al-action-icon--blue" />;
    case "Processing Failed":
      return <AlertTriangle size={16} className="al-action-icon al-action-icon--red" />;
    case "Document Deleted":
      return <Trash2 size={16} className="al-action-icon al-action-icon--orange" />;
    case "Integrity Check":
      return <ShieldCheck size={16} className="al-action-icon al-action-icon--blue" />;
    case "User Role Updated":
      return <UserCheck size={16} className="al-action-icon al-action-icon--blue" />;
    case "Verification Failed":
      return <AlertCircle size={16} className="al-action-icon al-action-icon--red" />;
    default:
      return <Info size={16} className="al-action-icon al-action-icon--gray" />;
  }
};

export const AuditLogs: React.FC = () => {
  // ── Filter States ──
  const [dateRange, setDateRange]   = useState<string>("Sep 1, 2026 – Sep 19, 2026");
  const [userFilter, setUserFilter] = useState<string>("all");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [resourceFilter, setResourceFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // ── Pagination State ──
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Filter computation
  const filteredLogs = useMemo(() => {
    return AUDIT_LOGS.filter((log) => {
      if (userFilter !== "all" && log.user !== userFilter) return false;
      if (actionFilter !== "all" && log.action !== actionFilter) return false;
      if (resourceFilter !== "all" && log.resource !== resourceFilter) return false;
      if (statusFilter !== "all" && log.status !== statusFilter) return false;
      return true;
    });
  }, [userFilter, actionFilter, resourceFilter, statusFilter]);

  // Reset pagination when filters change
  const handleFilterChange = (setter: React.Dispatch<React.SetStateAction<string>>, value: string) => {
    setter(value);
    setCurrentPage(1);
  };

  const handleClearFilters = () => {
    setDateRange("Sep 1, 2026 – Sep 19, 2026");
    setUserFilter("all");
    setActionFilter("all");
    setResourceFilter("all");
    setStatusFilter("all");
    setCurrentPage(1);
  };

  const isFiltered =
    userFilter !== "all" || actionFilter !== "all" || resourceFilter !== "all" || statusFilter !== "all";

  // Summary Card stats (calculated from all or filtered as appropriate for demo, matching wireframe numbers on initial view)
  const totalEvents = 142; // Hardcoded wireframe baseline count for exact visual alignment
  const successCount = 98;
  const warningCount = 32;
  const errorCount = 12;

  // Pagination calculation
  const totalItems = filteredLogs.length;
  const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE) || 1;
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const paginatedLogs = filteredLogs.slice(startIndex, startIndex + ITEMS_PER_PAGE);

  return (
    <AdminLayout title="Audit Logs">
      {/* ── Page Header Action Button ── */}
      <div className="al-page-header">
        <div>
          <p className="al-subtitle">Track all system activities, document processing events, and user actions.</p>
        </div>
        <button type="button" className="al-export-btn" title="Export Audit Logs">
          <Download size={15} />
          Export Logs
        </button>
      </div>

      {/* ── Filter Bar ── */}
      <div className="admin-card al-filter-card">
        <div className="al-filters-grid">
          {/* Date range picker simulation */}
          <div className="al-filter-group">
            <div className="al-date-input-wrap">
              <Calendar size={15} className="al-date-icon" />
              <input
                type="text"
                className="al-date-input"
                value={dateRange}
                onChange={(e) => setDateRange(e.target.value)}
                placeholder="Select date range"
              />
            </div>
          </div>

          {/* User filter */}
          <div className="al-filter-group">
            <label className="al-filter-label">User</label>
            <select
              className="admin-select al-filter-select"
              value={userFilter}
              onChange={(e) => handleFilterChange(setUserFilter, e.target.value)}
            >
              <option value="all">All Users</option>
              {AUDIT_USERS.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>

          {/* Action Type filter */}
          <div className="al-filter-group">
            <label className="al-filter-label">Action Type</label>
            <select
              className="admin-select al-filter-select"
              value={actionFilter}
              onChange={(e) => handleFilterChange(setActionFilter, e.target.value)}
            >
              <option value="all">All Actions</option>
              {AUDIT_ACTIONS.map((act) => (
                <option key={act} value={act}>
                  {act}
                </option>
              ))}
            </select>
          </div>

          {/* Resource filter */}
          <div className="al-filter-group">
            <label className="al-filter-label">Resource</label>
            <select
              className="admin-select al-filter-select"
              value={resourceFilter}
              onChange={(e) => handleFilterChange(setResourceFilter, e.target.value)}
            >
              <option value="all">All Resources</option>
              {AUDIT_RESOURCES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          {/* Status filter */}
          <div className="al-filter-group">
            <label className="al-filter-label">Status</label>
            <select
              className="admin-select al-filter-select"
              value={statusFilter}
              onChange={(e) => handleFilterChange(setStatusFilter, e.target.value)}
            >
              <option value="all">All Statuses</option>
              {AUDIT_STATUSES.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>

          {/* Clear button */}
          <button
            type="button"
            className="al-clear-btn"
            onClick={handleClearFilters}
            disabled={!isFiltered && dateRange === "Sep 1, 2026 – Sep 19, 2026"}
          >
            Clear Filters
          </button>
        </div>
      </div>

      {/* ── Summary Cards ── */}
      <div className="al-summary-row">
        {/* Total Events */}
        <div className="admin-card al-summary-card">
          <div className="al-summary-icon al-summary-icon--blue">
            <FileText size={20} />
          </div>
          <div className="al-summary-info">
            <span className="al-summary-num">{totalEvents}</span>
            <span className="al-summary-label">Total Events</span>
          </div>
        </div>

        {/* Successful Actions */}
        <div className="admin-card al-summary-card">
          <div className="al-summary-icon al-summary-icon--green">
            <CheckCircle2 size={20} />
          </div>
          <div className="al-summary-info">
            <span className="al-summary-num">{successCount}</span>
            <span className="al-summary-label">Successful Actions</span>
          </div>
        </div>

        {/* Warnings */}
        <div className="admin-card al-summary-card">
          <div className="al-summary-icon al-summary-icon--orange">
            <AlertCircle size={20} />
          </div>
          <div className="al-summary-info">
            <span className="al-summary-num">{warningCount}</span>
            <span className="al-summary-label">Warnings</span>
          </div>
        </div>

        {/* Errors */}
        <div className="admin-card al-summary-card">
          <div className="al-summary-icon al-summary-icon--red">
            <AlertTriangle size={20} />
          </div>
          <div className="al-summary-info">
            <span className="al-summary-num">{errorCount}</span>
            <span className="al-summary-label">Errors</span>
          </div>
        </div>
      </div>

      {/* ── Audit Table ── */}
      <div className="admin-card al-table-card">
        <div className="admin-table-wrap">
          <table className="admin-table al-table">
            <thead>
              <tr>
                <th style={{ width: "165px" }}>
                  <div className="al-th-cell">Timestamp</div>
                </th>
                <th style={{ width: "95px" }}>
                  <div className="al-th-cell">User</div>
                </th>
                <th style={{ width: "160px" }}>
                  <div className="al-th-cell">Action</div>
                </th>
                <th style={{ width: "180px" }}>
                  <div className="al-th-cell">Resource</div>
                </th>
                <th>
                  <div className="al-th-cell">Details</div>
                </th>
                <th style={{ width: "100px" }}>
                  <div className="al-th-cell">Status</div>
                </th>
                <th style={{ width: "120px" }}>
                  <div className="al-th-cell">IP Address</div>
                </th>
                <th style={{ width: "45px", textAlign: "right" }}></th>
              </tr>
            </thead>
            <tbody>
              {paginatedLogs.length > 0 ? (
                paginatedLogs.map((log) => (
                  <tr key={log.id}>
                    {/* Timestamp with icon */}
                    <td>
                      <div className="al-timestamp-cell">
                        {getActionIcon(log.action)}
                        <span className="al-timestamp-text">{log.timestamp}</span>
                      </div>
                    </td>

                    {/* User */}
                    <td>
                      <span className="al-user-cell">{log.user}</span>
                    </td>

                    {/* Action */}
                    <td>
                      <span className="al-action-cell">{log.action}</span>
                    </td>

                    {/* Resource */}
                    <td>
                      <span className="al-resource-cell">{log.resource}</span>
                    </td>

                    {/* Details */}
                    <td>
                      <span className="al-details-cell">{log.details}</span>
                    </td>

                    {/* Status Badge */}
                    <td>
                      <span
                        className={`al-status-badge al-status-badge--${log.status.toLowerCase()}`}
                      >
                        {log.status}
                      </span>
                    </td>

                    {/* IP Address */}
                    <td>
                      <span className="al-ip-cell">{log.ipAddress}</span>
                    </td>

                    {/* Actions / More */}
                    <td style={{ textAlign: "right" }}>
                      <button type="button" className="al-action-btn" title="More options">
                        <MoreHorizontal size={15} />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8}>
                    <div className="al-empty">
                      <Info size={28} className="al-empty-icon" />
                      <p className="al-empty-text">No audit logs found</p>
                      <p className="al-empty-sub">Try adjusting your filters or clear them.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ── Pagination Footer ── */}
        <div className="al-pagination">
          <span className="al-pagination-info">
            Showing {totalItems > 0 ? startIndex + 1 : 0}–{Math.min(startIndex + ITEMS_PER_PAGE, totalItems)} of {totalEvents} events
          </span>

          <div className="al-pagination-controls">
            <button
              type="button"
              className="al-page-btn"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              aria-label="Previous Page"
            >
              <ChevronLeft size={14} />
            </button>

            {/* Simulated 1, 2, 3, 4, 5 ... 15 pagination buttons matching reference */}
            {[1, 2, 3, 4, 5].map((page) => (
              <button
                key={page}
                type="button"
                className={`al-page-btn ${currentPage === page ? "al-page-btn--active" : ""}`}
                onClick={() => setCurrentPage(page)}
              >
                {page}
              </button>
            ))}
            <span className="al-page-ellipsis">…</span>
            <button
              type="button"
              className={`al-page-btn ${currentPage === 15 ? "al-page-btn--active" : ""}`}
              onClick={() => setCurrentPage(15)}
            >
              15
            </button>

            <button
              type="button"
              className="al-page-btn"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              aria-label="Next Page"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
};
