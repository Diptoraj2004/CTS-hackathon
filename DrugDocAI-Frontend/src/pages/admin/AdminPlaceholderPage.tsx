import React from "react";
import { AdminLayout } from "../../layouts/AdminLayout";
import { NavLink } from "react-router-dom";
import {
  BookOpen,
  UploadCloud,
  ScrollText,
  ShieldCheck as ShieldCheckIcon,
  Headphones,
  ArrowRight,
  type LucideIcon,
} from "lucide-react";

// Shared placeholder for all non-Dashboard admin screens
const PLACEHOLDER_PAGES: Record<
  string,
  { title: string; icon: LucideIcon; desc: string }
> = {
  library:   { title: "Document Library",    icon: BookOpen,        desc: "Browse, search and manage all medical source documents." },
  upload:    { title: "Upload / Processing", icon: UploadCloud,     desc: "Upload new documents and monitor the processing pipeline." },
  audit:     { title: "Audit Logs",          icon: ScrollText,      desc: "Review all system and user actions for compliance and debugging." },
  integrity: { title: "Verify Integrity",    icon: ShieldCheckIcon, desc: "Run verification checks on processed documents." },
  support:   { title: "Human Support",       icon: Headphones,      desc: "Manage escalations, support queue and expert conversations." },
};

interface AdminPlaceholderPageProps {
  section: keyof typeof PLACEHOLDER_PAGES;
}

export const AdminPlaceholderPage: React.FC<AdminPlaceholderPageProps> = ({ section }) => {
  const page = PLACEHOLDER_PAGES[section];
  const Icon = page.icon;

  return (
    <AdminLayout title={page.title}>
      <div className="admin-placeholder-body">
        <div className="admin-placeholder-card">
          <div className="admin-placeholder-icon-wrap">
            <Icon size={36} />
          </div>
          <h2 className="admin-placeholder-heading">{page.title}</h2>
          <p className="admin-placeholder-desc">{page.desc}</p>
          <p className="admin-placeholder-note">
            This section is coming soon. The UI and backend integration will be built in a future sprint.
          </p>
          <NavLink to="/admin" className="admin-placeholder-back">
            ← Back to Dashboard <ArrowRight size={14} />
          </NavLink>
        </div>
      </div>
    </AdminLayout>
  );
};
