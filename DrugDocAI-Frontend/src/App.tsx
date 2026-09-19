import React from "react";
import { Routes, Route } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { MedicationSelect } from "./pages/MedicationSelect";
import { Login } from "./pages/Login";
import { AdminPlaceholder } from "./pages/AdminPlaceholder";
import { AskQuestion } from "./pages/AskQuestion";
import { ResultsPlaceholder } from "./pages/ResultsPlaceholder";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/admin" element={<AdminPlaceholder />} />
      <Route path="/select" element={<MedicationSelect />} />
      <Route path="/results" element={<AskQuestion />} />
      <Route path="/docs" element={<ResultsPlaceholder />} />
      <Route path="*" element={<Landing />} />
    </Routes>
  );
}

export default App;