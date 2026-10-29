import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { AppLayout, AuthLayout } from "@/components/layout/Layout";

import Landing from "@/pages/auth/Landing";
import Login from "@/pages/auth/Login";
import Register from "@/pages/auth/Register";

import StudentDashboard from "@/pages/student/Dashboard";
import Catalog from "@/pages/student/Catalog";
import MyCourses from "@/pages/student/MyCourses";
import CoursePage from "@/pages/student/CoursePage";
import LabPage from "@/pages/student/LabPage";
import TestPage from "@/pages/student/TestPage";
import ExamPage from "@/pages/student/ExamPage";
import ChatPage from "@/pages/student/ChatPage";
import Progress from "@/pages/student/Progress";
import Profile from "@/pages/student/Profile";

import TeacherDashboard from "@/pages/teacher/Dashboard";
import TeacherCourses from "@/pages/teacher/Courses";
import CourseEdit from "@/pages/teacher/CourseEdit";
import CourseView from "@/pages/teacher/CourseView";
import LabsManage from "@/pages/teacher/LabsManage";
import ReportsQueue from "@/pages/teacher/ReportsQueue";
import ReportReview from "@/pages/teacher/ReportReview";
import Analytics from "@/pages/teacher/Analytics";
import Students from "@/pages/teacher/Students";
import Requests from "@/pages/teacher/Requests";
import CourseFiles from "@/pages/teacher/CourseFiles";
import SystemPage from "@/pages/teacher/SystemPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AuthLayout />}>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
            </Route>

            <Route element={<AppLayout role="student" />}>
              <Route path="/student/dashboard" element={<StudentDashboard />} />
              <Route path="/student/my-courses" element={<MyCourses />} />
              <Route path="/student/catalog" element={<Catalog />} />
              <Route path="/student/courses/:id" element={<CoursePage />} />
              <Route path="/student/courses/:id/labs/:labId" element={<LabPage />} />
              <Route path="/student/courses/:id/test" element={<TestPage />} />
              <Route path="/student/courses/:id/exam" element={<ExamPage />} />
              <Route path="/student/courses/:id/chat" element={<ChatPage />} />
              <Route path="/student/progress" element={<Progress />} />
              <Route path="/student/profile" element={<Profile />} />
            </Route>

            <Route element={<AppLayout role="teacher" />}>
              <Route path="/teacher/dashboard" element={<TeacherDashboard />} />
              <Route path="/teacher/courses" element={<TeacherCourses />} />
              <Route path="/teacher/courses/new" element={<CourseEdit />} />
              <Route path="/teacher/courses/:id" element={<CourseView />} />
              <Route path="/teacher/courses/:id/edit" element={<CourseEdit />} />
              <Route path="/teacher/courses/:id/labs" element={<LabsManage />} />
              <Route path="/teacher/courses/:id/analytics" element={<Analytics />} />
              <Route path="/teacher/courses/:id/students" element={<Students />} />
              <Route path="/teacher/courses/:id/requests" element={<Requests />} />
              <Route path="/teacher/courses/:id/files" element={<CourseFiles />} />
              <Route path="/teacher/reports" element={<ReportsQueue />} />
              <Route path="/teacher/reports/:reportId" element={<ReportReview />} />
              <Route path="/teacher/system" element={<SystemPage />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        {/* тема уведомлений следует теме интерфейса (см. components/ui/sonner.tsx) */}
        <Toaster richColors position="bottom-right" />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
