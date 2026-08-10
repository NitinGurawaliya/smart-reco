import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X, Sparkles } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { eventTracker } from "@/lib/eventTracker";

export function Nav() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    eventTracker.stop();
    logout();
  };

  const navLinks = [
    { to: "/browse", label: "Browse" },
    ...(user?.role === "admin" ? [{ to: "/admin", label: "Admin" }] : []),
  ];

  const isActive = (path: string) =>
    path === "/browse"
      ? location.pathname === "/browse" || location.pathname.startsWith("/browse/")
      : location.pathname === path;

  return (
    <header className="sticky top-0 z-40 border-b border-[#D1CAB8] bg-[#0B1F33]">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          {/* Brand */}
          <Link to={user ? "/browse" : "/"} className="flex items-center gap-2 group">
            <Sparkles className="h-5 w-5 text-[#0F8B8D] group-hover:text-teal-300 transition-colors" />
            <span className="font-display text-lg font-semibold text-white tracking-tight">SmartReco</span>
          </Link>

          {/* Desktop nav */}
          {user && (
            <nav className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`px-3 py-1.5 text-sm rounded transition-colors ${
                    isActive(link.to)
                      ? "bg-[#0F8B8D]/20 text-[#0F8B8D]"
                      : "text-white/70 hover:text-white hover:bg-white/10"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          )}

          {/* Right side */}
          <div className="flex items-center gap-3">
            {user ? (
              <>
                <span className="hidden md:block text-xs text-white/50 truncate max-w-[160px]">{user.email}</span>
                <Button variant="outline" size="sm" onClick={handleLogout}
                  className="border-white/20 text-white/80 hover:bg-white/10 hover:text-white bg-transparent">
                  Logout
                </Button>
                <button className="md:hidden text-white/70 hover:text-white" onClick={() => setMobileOpen(!mobileOpen)}>
                  {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                </button>
              </>
            ) : (
              <div className="flex items-center gap-2">
                <Link to="/login">
                  <Button variant="ghost" size="sm" className="text-white/70 hover:text-white hover:bg-white/10">Login</Button>
                </Link>
                <Link to="/signup">
                  <Button size="sm">Sign up</Button>
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && user && (
        <div className="md:hidden border-t border-white/10 bg-[#0B1F33] px-4 pb-4 pt-2">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              onClick={() => setMobileOpen(false)}
              className={`block px-3 py-2 text-sm rounded mb-1 ${
                isActive(link.to) ? "bg-[#0F8B8D]/20 text-[#0F8B8D]" : "text-white/70 hover:text-white hover:bg-white/10"
              }`}
            >
              {link.label}
            </Link>
          ))}
          <div className="mt-2 pt-2 border-t border-white/10 text-xs text-white/40">{user.email}</div>
        </div>
      )}
    </header>
  );
}
