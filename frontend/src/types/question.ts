export type GradeLevel =
  | "phonics"
  | "elementary_low"
  | "elementary_mid"
  | "elementary_high"
  | "middle"
  | "high";

export type QuestionType =
  | "multiple_choice"
  | "fill_in_blank"
  | "reading_comprehension"
  | "grammar"
  | "vocabulary"
  | "short_answer";

export interface ChoiceItem {
  label: string;
  text: string;
}

export interface Question {
  id?: number;
  grade_level: GradeLevel;
  question_type: QuestionType;
  topic: string;
  difficulty: number;
  question_text: string;
  choices: ChoiceItem[] | null;
  correct_answer: string;
  explanation: string | null;
  passage: string | null;
}

export interface GenerateRequest {
  grade_level: GradeLevel;
  question_types: QuestionType[];
  topic: string;
  count: number;
  difficulty: number;
}

export interface GenerateResponse {
  questions: Question[];
  exam_set_id: string;
}

export const GRADE_LABELS: Record<GradeLevel, string> = {
  phonics: "파닉스",
  elementary_low: "초등 1-2학년",
  elementary_mid: "초등 3-4학년",
  elementary_high: "초등 5-6학년",
  middle: "중학교",
  high: "고등학교",
};

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  multiple_choice: "객관식 (4지선다)",
  fill_in_blank: "빈칸 채우기",
  reading_comprehension: "독해",
  grammar: "문법",
  vocabulary: "어휘",
  short_answer: "주관식 단답형",
};
