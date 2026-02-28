import { authFetch, getToken } from "@/lib/auth";
import type { ExamSet } from "@/types/auth";
import type { GenerateRequest, GenerateResponse, Question } from "@/types/question";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "API request failed");
  }
  return res.json();
}

export async function generateQuestions(req: GenerateRequest): Promise<GenerateResponse> {
  return fetchAPI<GenerateResponse>("/api/generate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getQuestions(params?: {
  exam_set_id?: string;
  grade_level?: string;
  limit?: number;
}): Promise<Question[]> {
  const searchParams = new URLSearchParams();
  if (params?.exam_set_id) searchParams.set("exam_set_id", params.exam_set_id);
  if (params?.grade_level) searchParams.set("grade_level", params.grade_level);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  const query = searchParams.toString();
  return fetchAPI<Question[]>(`/api/questions${query ? `?${query}` : ""}`);
}

export async function deleteQuestion(id: number): Promise<void> {
  await fetchAPI(`/api/questions/${id}`, { method: "DELETE" });
}

// Exam set CRUD
export async function listExams(): Promise<ExamSet[]> {
  return authFetch<ExamSet[]>("/api/exams");
}

export async function createExam(data: {
  title: string;
  grade_level: string;
  question_ids: number[];
}): Promise<ExamSet> {
  return authFetch<ExamSet>("/api/exams", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getExam(id: number): Promise<ExamSet & { questions: Question[] }> {
  return authFetch<ExamSet & { questions: Question[] }>(`/api/exams/${id}`);
}

export async function deleteExam(id: number): Promise<void> {
  await authFetch(`/api/exams/${id}`, { method: "DELETE" });
}
