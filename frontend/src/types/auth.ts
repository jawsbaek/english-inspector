export interface User {
  id: number;
  email: string;
  name: string;
  role: "user" | "admin";
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  name: string;
  password: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface ExamSet {
  id: number;
  title: string;
  grade_level: string;
  created_at: string;
  question_count: number;
}
