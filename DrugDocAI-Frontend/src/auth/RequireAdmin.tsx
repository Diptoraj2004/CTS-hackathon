import React from "react";
import { Navigate } from "react-router-dom";
import { isAdminKeyPresent } from "./adminApi";

/**
 * Wraps an admin page element. isAdminKeyPresent() checks sessionStorage for
 * a key that was actually validated against the backend at login time (see
 * mockAuth.login()) — not just "some localStorage user object exists," which
 * is the client-side-only check that was never wired to /admin/* at all
 * before this. Without a valid key, every admin API call 401s anyway; this
 * just stops the page from rendering in the first place and sends the
 * person to log in instead.
 */
export const RequireAdmin: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (!isAdminKeyPresent()) {
    return <Navigate to="/login#admin" replace />;
  }
  return <>{children}</>;
};
