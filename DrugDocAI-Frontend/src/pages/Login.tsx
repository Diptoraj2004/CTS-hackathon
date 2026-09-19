import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  User,
  Settings,
  ArrowRight,
  AlertCircle,
} from "lucide-react";
import { Header } from "../components/Header";
import { AppLayout } from "../layouts/AppLayout";
import { mockAuth } from "../auth/mockAuth";

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const [role, setRole] = useState<"user" | "admin">("user");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleRoleSwitch = (newRole: "user" | "admin") => {
    setRole(newRole);
    setError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!identifier.trim()) {
      setError(
        role === "admin"
          ? "Please enter your admin ID or email."
          : "Please enter your email or phone number."
      );
      return;
    }

    if (!password.trim()) {
      setError("Please enter your password.");
      return;
    }

    setIsLoading(true);
    try {
      const res = await mockAuth.login(identifier, password, role);
      if (res.success) {
        if (role === "admin") {
          navigate("/admin");
        } else {
          navigate("/select");
        }
      } else {
        setError(res.error || "Authentication failed. Please check your credentials.");
      }
    } catch {
      setError("An error occurred during authentication.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AppLayout className="login-page-layout">
      <Header showBackHome={true} />

      <section className="login-container container">
        {/* SURROUNDING PHARMACEUTICAL & BOTANICAL ACCENTS (LEFT) */}
        <div className="login-accents-left" aria-hidden="true">
          <div className="login-leaf login-leaf-left" />
          <div className="login-blister-pack blister-left">
            <div className="blister-pocket"><span className="blister-pill" /></div>
            <div className="blister-pocket"><span className="blister-pill" /></div>
            <div className="blister-pocket"><span className="blister-pill" /></div>
            <div className="blister-pocket"><span className="blister-pill" /></div>
          </div>
        </div>

        {/* MAIN LOGIN CARD */}
        <div className="login-card-wrap">
          <div className={`login-card ${role === "admin" ? "card-admin-mode" : "card-user-mode"}`}>
            {/* CARD HEADER */}
            <div className="login-card-header">
              <h1 className="login-title">
                {role === "admin" ? "Admin Access" : "Welcome to DrugDoc AI"}
              </h1>
              <p className="login-subtext">
                {role === "admin"
                  ? "Sign in to access the administration dashboard."
                  : "Sign in to continue to safer, evidence-based medication information."}
              </p>
            </div>

            {/* ROLE SELECTOR CARDS */}
            <div className="role-selector-grid">
              {/* USER ROLE CARD */}
              <div
                className={`role-card ${role === "user" ? "role-selected role-user-selected" : ""}`}
                onClick={() => handleRoleSwitch("user")}
                role="radio"
                aria-checked={role === "user"}
                tabIndex={0}
              >
                <div className="role-icon-circle role-icon-blush">
                  <User size={18} />
                </div>
                <div className="role-card-text">
                  <strong className="role-title">User</strong>
                  <span className="role-sub">Patient / Caregiver</span>
                </div>
                <span className={`role-radio-dot ${role === "user" ? "radio-dot-checked radio-dot-clay" : ""}`} />
              </div>

              {/* ADMIN ROLE CARD */}
              <div
                className={`role-card ${role === "admin" ? "role-selected role-admin-selected" : ""}`}
                onClick={() => handleRoleSwitch("admin")}
                role="radio"
                aria-checked={role === "admin"}
                tabIndex={0}
              >
                <div className="role-icon-circle role-icon-green">
                  <Settings size={18} />
                </div>
                <div className="role-card-text">
                  <strong className="role-title">Admin</strong>
                  <span className="role-sub">Administration</span>
                </div>
                <span className={`role-radio-dot ${role === "admin" ? "radio-dot-checked radio-dot-teal" : ""}`} />
              </div>
            </div>

            {/* ERROR ALERT */}
            {error && (
              <div className="login-error-banner">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            {/* LOGIN FORM */}
            <form onSubmit={handleSubmit} className="login-form">
              {/* IDENTIFIER FIELD */}
              <div className="form-group">
                <label className="form-label">
                  {role === "admin" ? "Admin ID or Email" : "Email or Phone"}
                </label>
                <div className="input-with-icon">
                  <Mail size={17} className="input-icon" />
                  <input
                    type="text"
                    className="form-input"
                    placeholder={
                      role === "admin"
                        ? "Enter your admin ID or email"
                        : "Enter your email or phone number"
                    }
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                  />
                </div>
              </div>

              {/* PASSWORD FIELD */}
              <div className="form-group">
                <label className="form-label">Password</label>
                <div className="input-with-icon">
                  <Lock size={17} className="input-icon" />
                  <input
                    type={showPassword ? "text" : "password"}
                    className="form-input password-input"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="password-toggle-btn"
                    onClick={role === "user" ? () => setShowPassword(!showPassword) : undefined}
                    onMouseDown={role === "admin" ? () => setShowPassword(true) : undefined}
                    onMouseUp={role === "admin" ? () => setShowPassword(false) : undefined}
                    onMouseLeave={role === "admin" ? () => setShowPassword(false) : undefined}
                    onTouchStart={role === "admin" ? () => setShowPassword(true) : undefined}
                    onTouchEnd={role === "admin" ? () => setShowPassword(false) : undefined}
                    aria-label={role === "admin" ? "Hold to show password" : (showPassword ? "Hide password" : "Show password")}
                  >
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
                <div className="forgot-password-wrap">
                  <a href="#forgot" className="forgot-password-link">
                    Forgot password?
                  </a>
                </div>
              </div>

              {/* SUBMIT BUTTON */}
              <button
                type="submit"
                className={`button button-large login-submit-btn ${role === "admin" ? "button-admin-primary" : "button-primary"
                  }`}
                disabled={isLoading}
              >
                {isLoading ? "Signing In..." : "Sign In"} <ArrowRight size={18} />
              </button>
            </form>

            {/* USER-ONLY EXTRA OPTIONS */}
            {role === "user" && (
              <div className="user-extra-options">
                <div className="login-or-divider">
                  <span>OR</span>
                </div>

                <button type="button" className="google-sign-in-btn">
                  <svg className="google-icon" width="18" height="18" viewBox="0 0 24 24">
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                    />
                  </svg>
                  <span>Continue with Google</span>
                </button>

                <div className="create-account-wrap">
                  <span>Don't have an account?</span>{" "}
                  <a href="#register" className="create-account-link">
                    Create one
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* SURROUNDING PHARMACEUTICAL & BOTANICAL ACCENTS (RIGHT) */}
        <div className="login-accents-right" aria-hidden="true">
          <div className="login-leaf login-leaf-right" />
          <div className="login-capsule-3d">
            <div className="capsule-half capsule-red" />
            <div className="capsule-half capsule-white" />
            <div className="capsule-shine" />
          </div>
          <div className="login-tablet login-tablet-1" />
          <div className="login-tablet login-tablet-2" />
          <div className="login-blister-pack blister-right">
            <div className="blister-pocket"><span className="blister-pill" /></div>
            <div className="blister-pocket"><span className="blister-pill" /></div>
            <div className="blister-pocket"><span className="blister-pill" /></div>
            <div className="blister-pocket"><span className="blister-pill" /></div>
          </div>
        </div>
      </section>

      {/* MINIMAL FOOTER FOR LOGIN PAGE: © 2026 DrugDoc AI */}
      <footer className="login-footer">
        <div className="container footer-content-minimal justify-center">
          <span>© 2026 DrugDoc AI</span>
        </div>
      </footer>
    </AppLayout>
  );
};
