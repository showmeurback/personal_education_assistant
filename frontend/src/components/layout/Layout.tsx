import { Navigate, Outlet, useLocation } from "react-router-dom";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { useAuthStore, type UserRole } from "@/store/authStore";
import { Sidebar } from "./Sidebar";

/** Каркас для авторизованного пользователя с проверкой роли. */
export function AppLayout({ role }: { role: UserRole }) {
  const { isAuthenticated, role: current } = useAuthStore();
  const { pathname } = useLocation();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (current !== role) return <Navigate to={current === "teacher" ? "/teacher/dashboard" : "/student/dashboard"} replace />;

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="lg:pl-64">
        <div className="px-4 py-6 sm:px-8 sm:py-8 max-w-6xl mx-auto">
          {/* ошибка одной страницы не обрушивает меню и не оставляет пустой экран */}
          <ErrorBoundary resetKey={pathname}>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}

export function AuthLayout() {
  const { isAuthenticated, role } = useAuthStore();
  if (isAuthenticated) {
    return <Navigate to={role === "teacher" ? "/teacher/dashboard" : "/student/dashboard"} replace />;
  }
  return <Outlet />;
}
