import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Login() {
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await login(email, password);
      navigate("/browse");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F4EF] flex items-center justify-center px-4">
      <div className="w-full max-w-sm animate-fade-in">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2 justify-center mb-8 group">
          <Sparkles className="h-5 w-5 text-[#0F8B8D]" />
          <span className="font-display text-xl font-semibold text-[#0B1F33]">SmartReco</span>
        </Link>

        <div className="bg-white border border-[#D1CAB8] rounded-xl p-8">
          <h1 className="font-display text-2xl font-semibold text-[#0B1F33] mb-1">Welcome back</h1>
          <p className="text-sm text-[#6B7280] mb-6">Sign in to your account</p>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>

        <p className="text-center text-sm text-[#6B7280] mt-5">
          No account?{" "}
          <Link to="/signup" className="text-[#0F8B8D] hover:underline font-medium">
            Sign up
          </Link>
        </p>

        <p className="text-center text-xs text-[#9CA3AF] mt-4">
          Admin demo: <span className="font-mono">admin@smartreco.dev</span> / <span className="font-mono">admin123</span>
        </p>
      </div>
    </div>
  );
}
