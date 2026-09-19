import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bell,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  FileText,
  UploadCloud,
  Database,
  User,
  ShieldCheck,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { AUDIT_LOGS, AuditLogRecord } from "../../data/adminData";

// ── Notification Data Abstraction ─────────────────────────────────────────────
// Structure designed so backend audit event handlers / WebSockets / SSE can easily
// push new events into state.
export interface NotificationItem {
  id: string;
  timestamp: string;
  action: string;
  resource: string;
  details: string;
  status: "Success" | "Warning" | "Error";
  isUnread: boolean;
}

// Transform mock AUDIT_LOGS into initial notification items
const getInitialNotifications = (): NotificationItem[] => {
  return AUDIT_LOGS.slice(0, 5).map((log) => ({
    id: log.id,
    timestamp: log.timestamp,
    action: log.action,
    resource: log.resource,
    details: log.details,
    status: log.status,
    isUnread: true,
  }));
};

// Icon helper per notification type
const getNotificationIcon = (action: string, status: string) => {
  if (status === "Error") {
    return <AlertCircle size={15} className="admin-notif-item-icon admin-notif-item-icon--error" />;
  }
  if (status === "Warning") {
    return <AlertTriangle size={15} className="admin-notif-item-icon admin-notif-item-icon--warning" />;
  }
  switch (action) {
    case "Document Processed":
      return <CheckCircle2 size={15} className="admin-notif-item-icon admin-notif-item-icon--success" />;
    case "File Uploaded":
      return <UploadCloud size={15} className="admin-notif-item-icon admin-notif-item-icon--teal" />;
    case "Document Indexed":
      return <Database size={15} className="admin-notif-item-icon admin-notif-item-icon--teal" />;
    case "Login":
      return <User size={15} className="admin-notif-item-icon admin-notif-item-icon--blue" />;
    default:
      return <ShieldCheck size={15} className="admin-notif-item-icon admin-notif-item-icon--teal" />;
  }
};

export const NotificationDropdown: React.FC = () => {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>(getInitialNotifications);
  
  // Track overall unread state (red dot)
  const hasUnread = notifications.some((n) => n.isUnread);

  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const toggleDropdown = () => {
    if (!isOpen) {
      setIsOpen(true);
      // Mark all current notifications as read upon opening
      setNotifications((prev) => prev.map((n) => ({ ...n, isUnread: false })));
    } else {
      setIsOpen(false);
    }
  };

  const handleShowMore = () => {
    setIsOpen(false);
    navigate("/admin/audit");
  };

  return (
    <div className="admin-notif-wrap" ref={containerRef}>
      <button
        type="button"
        className={`admin-notif-btn${isOpen ? " admin-notif-btn--active" : ""}`}
        onClick={toggleDropdown}
        aria-label="Notifications"
        aria-expanded={isOpen}
      >
        <Bell size={18} />
        {hasUnread && <span className="admin-notif-dot" aria-hidden="true" />}
      </button>

      {isOpen && (
        <div className="admin-notif-dropdown" role="dialog" aria-label="Notifications dropdown">
          {/* Header */}
          <div className="admin-notif-header">
            <span className="admin-notif-title">Audit Notifications</span>
            <span className="admin-notif-badge">
              {notifications.length} recent
            </span>
          </div>

          {/* List */}
          <div className="admin-notif-list">
            {notifications.map((item) => (
              <div key={item.id} className="admin-notif-item">
                <div className="admin-notif-item-left">
                  {getNotificationIcon(item.action, item.status)}
                </div>
                <div className="admin-notif-item-body">
                  <div className="admin-notif-item-header">
                    <span className="admin-notif-item-action">{item.action}</span>
                    <span className="admin-notif-item-time">{item.timestamp.split(" ").slice(-2).join(" ")}</span>
                  </div>
                  <p className="admin-notif-item-details">
                    {item.resource !== "—" ? `${item.resource} • ` : ""}
                    {item.details}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="admin-notif-footer">
            <button type="button" className="admin-notif-more-btn" onClick={handleShowMore}>
              <span>Show More</span>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
