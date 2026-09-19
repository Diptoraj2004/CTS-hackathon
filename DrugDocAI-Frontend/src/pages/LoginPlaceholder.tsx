import React from "react";
import { Link } from "react-router-dom";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";
import { AppLayout } from "../layouts/AppLayout";

export const LoginPlaceholder: React.FC = () => {
  return (
    <AppLayout>
      <Header showAvatar={false} />

      <section className="container f03-container">
        <div className="f03-card" style={{ maxWidth: "480px", margin: "40px auto", textAlign: "center" }}>
          <h2>Login</h2>
          <p style={{ color: "var(--slate)", margin: "12px 0 24px" }}>
            Authentication module placeholder for future implementation.
          </p>
          <Link to="/" className="button button-primary">
            Return to Landing
          </Link>
        </div>
      </section>

      <Footer isMinimal={true} />
    </AppLayout>
  );
};
