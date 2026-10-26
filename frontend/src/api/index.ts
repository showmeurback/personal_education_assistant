import { del, download, get, patch, post, put, upload } from "./client";
import type * as T from "./types";

export * from "./types";
export { errorMessage } from "./client";

export const authApi = {
  login: (login: string, password: string, role: "student" | "teacher") =>
    post<{ token: string; role: "student" | "teacher"; id: number; name: string }>("/auth/login", { login, password, role }),
  registerStudent: (data: { login: string; password: string; first_name: string; last_name: string; characteristic?: string; interests: string[] }) =>
    post<{ token: string; role: "student"; id: number; name: string }>("/auth/register/student", data),
  registerTeacher: (data: { login: string; password: string; first_name: string; last_name: string }) =>
    post<{ token: string; role: "teacher"; id: number; name: string }>("/auth/register/teacher", data),
};

export const meApi = {
  profile: () => get<{ id: number; login: string; first_name: string; last_name: string; characteristic: string | null }>("/me/profile"),
  updateCharacteristic: (characteristic: string) => put("/me/characteristic", { characteristic }),
  preferences: () => get<{ preferred_explanation_style: string | null; notes: string | null }>("/me/preferences"),
  updatePreferences: (data: { preferred_explanation_style: string; notes: string }) => put("/me/preferences", data),
  interests: () => get<{ interests: string[] }>("/me/interests").then((r) => r.interests),
  updateInterests: (interests: string[]) => put("/me/interests", { interests }),
  courses: () => get<T.MyCourse[]>("/me/courses"),
  recommendations: () => get<T.Recommendations>("/me/recommendations"),
  reports: () => get<{ reports: T.Report[] }>("/me/reports").then((r) => r.reports),
  weakTopics: (courseId: number, advice = true) =>
    get<T.WeakTopicsMap>(`/courses/${courseId}/weak-topics?advice=${advice}`),
  testResults: (courseId?: number) =>
    get<{ results: T.TestResult[] }>(`/me/test-results${courseId ? `?course_id=${courseId}` : ""}`).then((r) => r.results),
  examResults: (courseId?: number) =>
    get<{ results: T.ExamResult[] }>(`/me/exam-results${courseId ? `?course_id=${courseId}` : ""}`).then((r) => r.results),
  chats: () => get<T.Chat[]>("/me/chats"),
};

export const coursesApi = {
  list: () => get<T.Course[]>("/courses"),
  get: (id: number) => get<T.CourseDetails>(`/courses/${id}`),
  create: (data: { title: string; description: string; difficulty: string; tags: string[]; exam_questions: string }) =>
    post<{ course_id: number }>("/courses", data),
  update: (id: number, data: { title: string; description: string; difficulty: string; tags: string[]; exam_questions: string }) =>
    put(`/courses/${id}`, data),
  remove: (id: number) => del(`/courses/${id}`),
  students: (id: number) =>
    get<{ students: { id: number; first_name: string; last_name: string }[] }>(`/courses/${id}/students`).then((r) => r.students),
  requestAccess: (id: number) => post(`/courses/${id}/requests`),
  requests: (id: number) => get<{ requests: T.CourseRequest[] }>(`/courses/${id}/requests`).then((r) => r.requests),
  approveRequest: (requestId: number) => post(`/course-requests/${requestId}/approve`),
  rejectRequest: (requestId: number) => post(`/course-requests/${requestId}/reject`),
  files: (id: number) => get<{ files: T.CourseFile[] }>(`/courses/${id}/files`).then((r) => r.files),
  uploadFiles: (id: number, files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return upload<{ indexed: { filename: string; chunks: number }[]; errors: { filename: string; error: string }[] }>(`/courses/${id}/files`, fd);
  },
  deleteFile: (id: number, recordId: number) => del(`/courses/${id}/files/${recordId}`),
  downloadFile: (id: number, file: T.CourseFile) => download(`/courses/${id}/files/${file.file_id}/download`, file.filename),
  rate: (id: number, rating: number) => post(`/courses/${id}/rate`, { rating }),
  analytics: (id: number) => get<T.CourseAnalytics>(`/courses/${id}/analytics`),
  tags: () => get<{ tags: string[] }>("/tags").then((r) => r.tags),
};

export const labsApi = {
  list: (courseId: number) => get<T.Lab[]>(`/courses/${courseId}/labs`),
  get: (labId: number) => get<T.Lab>(`/labs/${labId}`),
  create: (courseId: number, data: Omit<T.Lab, "id" | "course_id">) => post(`/courses/${courseId}/labs`, data),
  update: (labId: number, data: Omit<T.Lab, "id" | "course_id">) => put(`/labs/${labId}`, data),
  remove: (labId: number) => del(`/labs/${labId}`),
};

export const reportsApi = {
  submit: (labId: number, data: { file?: File; url?: string }) => {
    const fd = new FormData();
    if (data.file) fd.append("file", data.file);
    if (data.url) fd.append("url", data.url);
    return upload<T.SubmitReportResult>(`/labs/${labId}/reports`, fd);
  },
  myLabReports: (labId: number) => get<{ reports: T.Report[] }>(`/labs/${labId}/my-reports`).then((r) => r.reports),
  get: (reportId: number) => get<{ report: T.Report; check: T.ReportCheck | null }>(`/reports/${reportId}`),
  downloadFile: (report: T.Report) => download(`/reports/${report.report_id}/file`, report.filename ?? "report"),
  setStatus: (reportId: number, status: "approved" | "not-approved", comment?: string) =>
    post(`/reports/${reportId}/status`, { status, comment }),
};

export const teacherApi = {
  courses: () => get<T.TeacherCourse[]>("/teacher/courses"),
  queue: () => get<{ reports: T.Report[] }>("/teacher/reports/queue").then((r) => r.reports),
  history: () => get<{ reports: T.Report[] }>("/teacher/reports/history").then((r) => r.reports),
  verificationStats: () => get<{ stats: T.VerificationStat[] }>("/teacher/verification-stats").then((r) => r.stats),
};

export const testsApi = {
  generate: (courseId: number, data: { topic: string; num_questions: number; difficulty: string }) =>
    post<T.GeneratedTest>(`/courses/${courseId}/tests/generate`, data),
  generateFromFile: (courseId: number, file: File, numQuestions: number, difficulty: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("num_questions", String(numQuestions));
    fd.append("difficulty", difficulty);
    return upload<T.GeneratedTest>(`/courses/${courseId}/tests/generate-from-file`, fd);
  },
  submit: (testId: string, answers: string[]) => post<T.TestSubmitResult>(`/tests/${testId}/submit`, { answers }),
  answers: (resultId: number) => get<{ answers: T.TestAnswerResult[] }>(`/test-results/${resultId}/answers`).then((r) => r.answers),
};

export const examApi = {
  start: (courseId: number, questionCount: number) =>
    post<{ exam_id: string; question: T.ExamQuestion; total_questions: number; has_more_questions: boolean }>(
      `/courses/${courseId}/exam/start`, { question_count: questionCount, language: "ru" }),
  answer: (courseId: number, examId: string, answer: string) =>
    post<{ evaluation: T.ExamEvaluation; next_question: T.ExamQuestion | null; completed: boolean }>(
      `/courses/${courseId}/exam/answer`, { exam_id: examId, answer }),
  summary: (courseId: number, examId: string) =>
    get<{ avg_score: number | null; results: T.ExamEvaluation[] }>(`/courses/${courseId}/exam/summary?exam_id=${examId}`),
  answers: (resultId: number) => get<{ answers: T.ExamEvaluation[] }>(`/exam-results/${resultId}/answers`).then((r) => r.answers),
};

export const chatApi = {
  create: (courseId: number) => post<{ chat_id: number; name: string }>("/chats", { course_id: courseId }),
  rename: (chatId: number, name: string) => patch(`/chats/${chatId}`, { name }),
  remove: (chatId: number) => del(`/chats/${chatId}`),
  history: (chatId: number) =>
    get<{ role: string; content: string }[]>(`/chats/${chatId}/messages`).then((rows) =>
      rows.map((m) => ({ role: m.role === "human" ? "user" : "assistant", content: m.content }) as T.ChatMessage)),
  send: (chatId: number, message: string) =>
    post<{ response: string; tools: string[]; sources: string[] }>(`/chats/${chatId}/messages`, { message }),
};

export const systemApi = {
  config: () => get<T.SystemConfig>("/system/config"),
};
