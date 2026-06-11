import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

/**
 * AuthCallback handles Emergent Google OAuth redirect.
 * URL pattern: /#session_id=<id>
 * We exchange the session_id with our backend → backend returns our JWT cookies +
 * user payload → we hydrate AuthContext and redirect to /.
 *
 * REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
 */
export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    const session_id = match ? decodeURIComponent(match[1]) : null;

    if (!session_id) {
      navigate("/login", { replace: true });
      return;
    }

    (async () => {
      try {
        const { data } = await api.post("/auth/google/session", { session_id });
        if (setUser && data?.user) setUser(data.user);
        // Clear the fragment so refresh doesn't re-process
        window.history.replaceState({}, document.title, "/");
        // Force reload so AuthContext picks up cookie-set state cleanly
        window.location.replace("/");
      } catch (err) {
        console.error("Google sign-in failed:", err);
        navigate("/login?error=google-failed", { replace: true });
      }
    })();
  }, [navigate, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center" data-testid="auth-callback">
      <div className="text-center">
        <div className="w-12 h-12 mx-auto mb-4 rounded-xl flex items-center justify-center animate-pulse" style={{ background: "#FF6B00" }}>
          <svg className="w-6 h-6 text-white animate-spin" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.3"/>
            <path d="M12 2 A 10 10 0 0 1 22 12" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
          </svg>
        </div>
        <p className="text-sm font-medium" style={{ color: "#0A101D", fontFamily: "Outfit" }}>Signing you in…</p>
        <p className="text-xs mt-1" style={{ color: "#64748B" }}>Just a moment.</p>
      </div>
    </div>
  );
}
