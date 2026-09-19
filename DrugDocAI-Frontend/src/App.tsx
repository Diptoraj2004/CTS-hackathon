import React from "react";
import { Routes, Route } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { MedicationSelect } from "./pages/MedicationSelect";
import { Login } from "./pages/Login";
import { AskQuestion } from "./pages/AskQuestion";
import { ResultsPlaceholder } from "./pages/ResultsPlaceholder";
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
      <Route path="/docs" element={<ResultsPlaceholder />} />

      {/* ── Admin flow ── */}
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="/admin/library"   element={<DocumentLibrary />} />
      <Route path="/admin/upload"    element={<UploadProcessing />} />
      <Route path="/admin/audit"     element={<AuditLogs />} />
      <Route path="/admin/integrity" element={<AdminPlaceholderPage section="integrity" />} />
      <Route path="/admin/support"   element={<AdminPlaceholderPage section="support" />} />

      {/* ── Fallback ── */}
      <Route path="*" element={<Landing />} />
    </Routes>
  );
}

export default App;