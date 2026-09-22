import React from "react";
import { Leaf } from "lucide-react";

interface FooterProps {
  isMinimal?: boolean;
}

export const Footer: React.FC<FooterProps> = ({ isMinimal = false }) => {
  if (isMinimal) {
    return (
      <footer className="landing-footer minimal-footer">
        <div className="container footer-content-minimal">
          <span>© 2026 DrugDoc AI</span>
          <span className="footer-sep">|</span>
          <span className="footer-links">
            Evidence-based <span className="dot">•</span> Audit-logged <span className="dot">•</span> Privacy <span className="dot">•</span> Terms
          </span>
        </div>
      </footer>
    );
  }

  return (
    <footer className="landing-footer">
      <div className="container footer-content">
        <div className="footer-left">
          <span>© 2026 DrugDoc AI</span>
          <span className="footer-sep">|</span>
          <span className="footer-links">
            Evidence-based <span className="dot">•</span> Audit-logged <span className="dot">•</span> Privacy <span className="dot">•</span> Terms
          </span>
        </div>
        <div className="footer-right">
          <Leaf size={14} className="footer-leaf-icon" />
          <span className="footer-tagline">Built for a healthier, more informed world.</span>
        </div>
      </div>
    </footer>
  );
};
