export type Difficulty = "beginner" | "intermediate" | "advanced";

export interface Course {
  id: number;
  title: string;
  teacher_id?: number;
  description: string | null;
  difficulty: Difficulty;
  created_at: string | null;
  tags: string[];
  enrolled?: boolean;
}

export interface CourseDetails extends Course {
  has_materials: boolean;
  is_owner: boolean;
  exam_questions?: string;
  enrolled?: boolean;
  request_status?: string | null;
}

export interface MyCourse extends Course {
  labs_completed: boolean;
  exam_completed: boolean;
  is_completed: boolean;
  my_rating: number | null;
}

export interface TeacherCourse extends Course {
  students: number;
  pending_requests: number;
  pending_reports: number;
}

export interface RecommendedCourse extends Course {
  score: number;
  tag_match: number;
  bayesian_rating: number;
  enrollment_count: number;
  signals: Record<string, number>;
  explanation: string[];
}

export interface Recommendations {
  recommended: RecommendedCourse[];
  other: RecommendedCourse[];
  has_recommendations: boolean;
  maybe_like: RecommendedCourse | null;
}

export interface Lab {
  id: number;
  number: number;
  title: string;
  task: string;
  course_id?: number;
  min_words: number | null;
  required_sections: string | null;
}

export interface CourseFile {
  id: number;
  filename: string;
  file_id: string;
  created_at: string;
}

export interface CourseRequest {
  id: number;
  student_id: number;
  course_id: number;
  status: string;
  created_at: string;
  first_name: string;
  last_name: string;
}

export type StepStatus = "pass" | "fail" | "warn" | "info";

export interface ProtocolStep {
  step: number;
  order: number;
  title: string;
  component: string;
  kind: "symbolic" | "neural";
  status: StepStatus;
  duration_ms: number;
  details: Record<string, unknown>;
}

export interface ReportCheck {
  decision: "approve" | "reject" | "manual_review";
  decided_by: string;
  final_score: number | null;
  max_similarity: number | null;
  llm_calls: number;
  duration_ms: number;
  protocol?: ProtocolStep[];
  created_at: string;
}

export interface Report {
  report_id: number;
  student_id: number;
  student_name: string;
  course_id: number;
  course_title: string;
  lab_id: number;
  lab_number: number;
  lab_title: string;
  url: string | null;
  source_type: "gdoc" | "file";
  filename: string | null;
  status: string;
  comment: string | null;
  ai_summary: string | null;
  created_at: string;
  text?: string;
  check?: ReportCheck | null;
}

/** Ответ на сдачу отчёта: 202 — отчёт принят и проверяется в фоне (status = "checking"). */
export interface SubmitReportResult {
  report_id: number;
  status: string;
  message: string;
  decision?: string;
  decided_by?: string;
  reason?: string;
  score?: number | null;
  llm_calls?: number;
  duration_ms?: number;
  protocol?: ProtocolStep[];
}

export interface TestQuestion {
  question_num: number;
  text: string;
  options: Record<string, string>;
  type: string;
}

export interface GeneratedTest {
  test_id: string;
  difficulty: string;
  total_questions: number;
  questions: TestQuestion[];
}

export interface TestAnswerResult {
  question_num: number;
  question_text: string;
  options: Record<string, string>;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  /** разбор ошибки нейросетевым агентом (только для неверных ответов) */
  explanation?: string | null;
}

export interface TestSubmitResult {
  total_questions: number;
  correct_answers: number;
  wrong_answers: number;
  percentage: number;
  grade: string;
  grade_description: string;
  results: TestAnswerResult[];
}

export interface TestResult {
  id: number;
  course_id: number;
  topic: string | null;
  source: string;
  difficulty: string;
  total_questions: number;
  correct_answers: number;
  wrong_answers: number;
  percentage: number;
  created_at: string;
}

export interface ExamQuestion {
  id: number;
  text: string;
}

export interface ExamEvaluation {
  question_id: number;
  question_text: string;
  user_answer: string;
  verdict: "correct" | "partial" | "incorrect";
  recommendation: string;
  issues: string[];
  score: string | null;
  summary: string | null;
}

export interface ExamResult {
  id: number;
  course_id: number;
  total_questions: number;
  avg_score: number | null;
  completed: boolean;
  created_at: string;
}

export interface Chat {
  chat_id: number;
  name: string;
  course_id: number;
  course_title: string;
  created_at: string;
  /** закреплённые чаты идут в списке первыми */
  pinned: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  tools?: string[];
  sources?: string[];
  /** шаги агента, показанные во время потокового ответа */
  steps?: string[];
  /** ответ ещё генерируется */
  streaming?: boolean;
  /** время отправки (ISO 8601, UTC) */
  created_at?: string;
}

export type ChatStreamEvent =
  | { type: "step"; text: string }
  | { type: "token"; text: string }
  | { type: "reset" }
  | { type: "done"; response: string; tools: string[]; sources: string[]; asked_at?: string; answered_at?: string }
  | { type: "error"; detail: string };

export interface CourseAnalytics {
  test_averages: { student_id: number; first_name: string; last_name: string; test_count: number; avg_percentage: number | null }[];
  exam_averages: { student_id: number; first_name: string; last_name: string; exam_count: number; avg_score: number | null }[];
  report_statuses: { student_id: number; first_name: string; last_name: string; lab_title: string; status: string }[];
  test_timeline: { student_id: number; percentage: number | null; topic: string; created_at: string }[];
  topic_accuracy: { topic: string; total_q: number; correct_q: number; accuracy_pct: number; test_count: number }[];
  hard_questions: { question_text: string; attempts: number; correct: number; success_rate: number; topic: string }[];
  difficulty_breakdown: { difficulty: string; test_count: number; avg_pct: number }[];
  verdict_distribution: { verdict: string; count: number }[];
  lab_funnel: { id: number; number: number; title: string; enrolled: number; submitted: number; approved: number; rejected: number }[];
  verification: VerificationStat[];
}

export interface VerificationStat {
  decision: string;
  decided_by: string;
  count: number;
  avg_ms: number;
  avg_llm_calls: number;
}

export interface SystemConfig {
  llm: {
    provider: string; model: string; judge_model: string; base_url: string; configured: boolean;
    judge_models?: Record<"strict" | "objective" | "loyal", string>; feedback_model?: string;
  };
  embeddings: { provider: string; model: string };
  vision?: { enabled: boolean; model: string; max_images: number };
  verification: Record<string, number>;
}

/** Карта пробелов: слабые темы курса с уровнем освоения и советом. */
export interface WeakTopic {
  topic: string;
  mastery: number;
  level: string;
  evidence: { test: number; exam: number; lab: number };
  details: string[];
  advice: string;
  sources: { filename: string; snippet: string }[];
}

export interface WeakTopicsMap {
  topics: WeakTopic[];
  strong: { topic: string; mastery: number }[];
  evidence_total: number;
  llm_used: boolean;
  with_advice: boolean;
  method: string;
}
