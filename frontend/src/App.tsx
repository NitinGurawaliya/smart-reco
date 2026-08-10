import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { RecommendationProvider, useRecommendation } from "@/contexts/RecommendationContext";
import { eventTracker } from "@/lib/eventTracker";
import { Nav } from "@/components/Nav";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import Browse from "@/pages/Browse";
import CourseDetail from "@/pages/CourseDetail";
import Admin from "@/pages/Admin";
import { RecommendationToast } from "@/components/RecommendationToast";

function PageFade() {
  const location = useLocation();
  return (
    <div key={location.pathname} className="animate-fade-in min-h-[calc(100vh-56px)]">
      <Outlet />
    </div>
  );
}

function AuthenticatedLayout() {
  const { user } = useAuth();
  const { setFromEventBatch } = useRecommendation();

  useEffect(() => {
    if (!user) return;
    eventTracker.setOnTriggered(setFromEventBatch);
    eventTracker.start();
    return () => {
      eventTracker.stop();
    };
  }, [user, setFromEventBatch]);

  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-[#F7F4EF]">
      <Nav />
      <PageFade />
      <RecommendationToast />
    </div>
  );
}

function AdminGuard() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/browse" replace />;
  return <Outlet />;
}

function PublicRoute() {
  const { user } = useAuth();
  if (user) return <Navigate to="/browse" replace />;
  return <Outlet />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicRoute />}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
      </Route>

      <Route element={<AuthenticatedLayout />}>
        <Route path="/browse" element={<Browse />} />
        <Route path="/browse/:courseId" element={<CourseDetail />} />
        {/* Legacy For You URL → Browse (single-page product) */}
        <Route path="/app" element={<Navigate to="/browse" replace />} />
        <Route element={<AdminGuard />}>
          <Route path="/admin" element={<Admin />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RecommendationProvider>
          <AppRoutes />
        </RecommendationProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
