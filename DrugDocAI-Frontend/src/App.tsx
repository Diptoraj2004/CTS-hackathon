import React from "react";
import { Routes, Route } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { MedicationSelect } from "./pages/MedicationSelect";
import { Login } from "./pages/Login";
import { AskQuestion } from "./pages/AskQuestion";
import { SourcesEvidence } from "./pages/SourcesEvidence";
import { MedicationInfo } from "./pages/MedicationInfo";
import { ResultsPlaceholder } from "./pages/ResultsPlaceholder";
import { ProfilePlaceholder } from "./pages/ProfilePlaceholder";
import { RequireAdmin } from "./auth/RequireAdmin";
import { AdminDashboard } from "./pages/admin/AdminDashboard";
import { AdminPlaceholderPage } from "./pages/admin/AdminPlaceholderPage";
import { DocumentLibrary } from "./pages/admin/DocumentLibrary";
import { UploadProcessing } from "./pages/admin/UploadProcessing";
import { AuditLogs } from "./pages/admin/AuditLogs";

function App() {
  return (
    <Routes>
      {/* ── User flow ── */}
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/select" element={<MedicationSelect />} />
      <Route path="/results" element={<AskQuestion />} />
      <Route path="/sources" element={<SourcesEvidence />} />
      <Route path="/medication-info" element={<MedicationInfo />} />
      <Route path="/docs" element={<ResultsPlaceholder />} />
      <Route path="/profile" element={<ProfilePlaceholder />} />

      {/* ── Admin flow — every route requires a validated admin key ── */}
      <Route path="/admin" element={<RequireAdmin><AdminDashboard /></RequireAdmin>} />
      <Route path="/admin/library"   element={<RequireAdmin><DocumentLibrary /></RequireAdmin>} />
      <Route path="/admin/upload"    element={<RequireAdmin><UploadProcessing /></RequireAdmin>} />
      <Route path="/admin/audit"     element={<RequireAdmin><AuditLogs /></RequireAdmin>} />
      <Route path="/admin/integrity" element={<RequireAdmin><AdminPlaceholderPage section="integrity" /></RequireAdmin>} />
      <Route path="/admin/support"   element={<RequireAdmin><AdminPlaceholderPage section="support" /></RequireAdmin>} />

      {/* ── Fallback ── */}
      <Route path="*" element={<Landing />} />
    </Routes>
  );
}

export default App;