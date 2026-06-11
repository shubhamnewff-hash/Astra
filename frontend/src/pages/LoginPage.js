import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Sparkles, Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const { login, register } = useAuth();
  const [tab, setTab] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }
    setLoading(true);
    try {
      await register(email, password, name);
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const handleGoogleLogin = () => {
    const redirectUrl = window.location.origin + '/';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const GoogleButton = () => (
    <>
      <Button type="button" onClick={handleGoogleLogin} variant="outline"
        className="w-full h-11 font-medium border-[#E2E8F0] hover:bg-[#F8FAFC]"
        data-testid="google-login-button">
        <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24">
          <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
          <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
          <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC04"/>
          <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
        </svg>
        Continue with Google
      </Button>
      <div className="relative my-5">
        <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[#E2E8F0]" /></div>
        <div className="relative flex justify-center text-xs"><span className="bg-white px-3" style={{ color: '#64748B' }}>or</span></div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Left side - Brand */}
      <div className="hidden lg:flex lg:w-[45%] relative overflow-hidden items-center justify-center"
           style={{ background: 'linear-gradient(135deg, #0A101D 0%, #0F172A 100%)' }}>
        <div className="absolute inset-0 opacity-10"
             style={{ backgroundImage: 'radial-gradient(circle at 30% 40%, #FF6B00 0%, transparent 50%), radial-gradient(circle at 70% 80%, #FF6B00 0%, transparent 50%)' }} />
        <div className="relative z-10 px-16 max-w-lg">
          <div className="flex items-center gap-3 mb-10">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: '#FF6B00' }}>
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <span className="text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>Astra</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white mb-6 tracking-tight" style={{ fontFamily: 'Outfit' }}>
            Your AI Knowledge Assistant
          </h1>
          <p className="text-lg text-slate-400 leading-relaxed">
            Get instant answers about Biziverse features, workflows, and troubleshooting. 
            Powered by your organization's approved knowledge base.
          </p>
          <div className="mt-12 flex gap-8">
            <div>
              <div className="text-2xl font-bold text-white">Instant</div>
              <div className="text-sm text-slate-500">Answers</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-white">Structured</div>
              <div className="text-sm text-slate-500">Responses</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-white">24/7</div>
              <div className="text-sm text-slate-500">Available</div>
            </div>
          </div>
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-white">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: '#FF6B00' }}>
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <span className="text-2xl font-bold" style={{ fontFamily: 'Outfit', color: '#0A101D' }}>Astra</span>
          </div>

          <Tabs value={tab} onValueChange={(v) => { setTab(v); setError(""); }}>
            <TabsList className="w-full mb-8 bg-[#F1F5F9]">
              <TabsTrigger value="login" className="flex-1 data-[state=active]:bg-white data-[state=active]:text-[#0A101D] data-[state=active]:shadow-sm" data-testid="login-tab">
                Sign In
              </TabsTrigger>
              <TabsTrigger value="register" className="flex-1 data-[state=active]:bg-white data-[state=active]:text-[#0A101D] data-[state=active]:shadow-sm" data-testid="register-tab">
                Create Account
              </TabsTrigger>
            </TabsList>

            <TabsContent value="login">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold tracking-tight" style={{ fontFamily: 'Outfit', color: '#0A101D' }}>Welcome back</h2>
                <p className="text-sm mt-1" style={{ color: '#64748B' }}>Sign in to continue to Astra</p>
              </div>
              <form onSubmit={handleLogin} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="login-email" className="text-sm font-medium" style={{ color: '#334155' }}>Email</Label>
                  <Input id="login-email" type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} required
                    className="h-11 border-[#E2E8F0] focus:border-[#FF6B00] focus:ring-[#FF6B00]" data-testid="login-email-input" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="login-password" className="text-sm font-medium" style={{ color: '#334155' }}>Password</Label>
                  <div className="relative">
                    <Input id="login-password" type={showPw ? "text" : "password"} placeholder="Enter password" value={password} onChange={(e) => setPassword(e.target.value)} required
                      className="h-11 pr-10 border-[#E2E8F0] focus:border-[#FF6B00] focus:ring-[#FF6B00]" data-testid="login-password-input" />
                    <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#334155]" onClick={() => setShowPw(!showPw)} tabIndex={-1}>
                      {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
                {error && <p className="text-sm text-[#EF4444]" data-testid="auth-error">{error}</p>}
                <Button type="submit" disabled={loading} className="w-full h-11 text-white font-semibold"
                  style={{ background: '#FF6B00' }}
                  data-testid="login-submit-button">
                  {loading ? "Signing in..." : "Sign In"}
                </Button>
                <div className="text-center">
                  <Link to="/forgot-password" className="text-sm font-medium text-[#FF6B00] hover:underline" data-testid="forgot-password-link">
                    Forgot password?
                  </Link>
                </div>
              </form>
            </TabsContent>

            <TabsContent value="register">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold tracking-tight" style={{ fontFamily: 'Outfit', color: '#0A101D' }}>Get Started</h2>
                <p className="text-sm mt-1" style={{ color: '#64748B' }}>Create your Astra account</p>
              </div>
              <GoogleButton />
              <form onSubmit={handleRegister} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="reg-name" className="text-sm font-medium" style={{ color: '#334155' }}>Full Name</Label>
                  <Input id="reg-name" type="text" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} required
                    className="h-11 border-[#E2E8F0] focus:border-[#FF6B00] focus:ring-[#FF6B00]" data-testid="register-name-input" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="reg-email" className="text-sm font-medium" style={{ color: '#334155' }}>Email</Label>
                  <Input id="reg-email" type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} required
                    className="h-11 border-[#E2E8F0] focus:border-[#FF6B00] focus:ring-[#FF6B00]" data-testid="register-email-input" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="reg-password" className="text-sm font-medium" style={{ color: '#334155' }}>Password</Label>
                  <div className="relative">
                    <Input id="reg-password" type={showPw ? "text" : "password"} placeholder="Min 6 characters" value={password} onChange={(e) => setPassword(e.target.value)} required
                      className="h-11 pr-10 border-[#E2E8F0] focus:border-[#FF6B00] focus:ring-[#FF6B00]" data-testid="register-password-input" />
                    <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#334155]" onClick={() => setShowPw(!showPw)} tabIndex={-1}>
                      {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
                {error && <p className="text-sm text-[#EF4444]" data-testid="auth-error">{error}</p>}
                <Button type="submit" disabled={loading} className="w-full h-11 text-white font-semibold"
                  style={{ background: '#FF6B00' }}
                  data-testid="register-submit-button">
                  {loading ? "Creating account..." : "Create Account"}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
