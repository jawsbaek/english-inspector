"use client";

import { useState, useEffect } from "react";
import GenerateForm from "@/components/GenerateForm";
import QuestionCard from "@/components/QuestionCard";
import ExamExportDialog from "@/components/ExamExportDialog";
import UserMenu from "@/components/UserMenu";
import SaveExamDialog from "@/components/SaveExamDialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { generateQuestions, deleteQuestion } from "@/lib/api";
import { getCurrentUser } from "@/lib/auth";
import type { Question, GenerateRequest } from "@/types/question";
import { GRADE_LABELS } from "@/types/question";
import type { User } from "@/types/auth";
import { Save } from "lucide-react";

export default function Home() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [examSetId, setExamSetId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAllAnswers, setShowAllAnswers] = useState(false);
  const [lastRequest, setLastRequest] = useState<GenerateRequest | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);

  // Hydrate user from localStorage after mount
  useEffect(() => {
    setUser(getCurrentUser());
  }, []);

  const handleGenerate = async (req: GenerateRequest) => {
    setIsLoading(true);
    setError(null);
    setLastRequest(req);
    try {
      const res = await generateQuestions(req);
      setQuestions(res.questions);
      setExamSetId(res.exam_set_id);
      setShowAllAnswers(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "문항 생성에 실패했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (id: number | undefined, index: number) => {
    if (id) {
      try {
        await deleteQuestion(id);
      } catch {
        // Still remove from UI even if API fails
      }
    }
    setQuestions((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="container mx-auto flex items-center justify-between px-4 py-4">
          <div>
            <h1 className="text-2xl font-bold">English Inspector</h1>
            <p className="text-sm text-muted-foreground">
              영어 시험지 자동 생성 및 검수 시스템
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="text-xs hidden sm:flex">
              DSPy 3.0 + MIPROv2
            </Badge>
            <UserMenu user={user} onUserChange={setUser} />
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
          <div className="print:hidden">
            <GenerateForm onGenerate={handleGenerate} isLoading={isLoading} />
          </div>

          <div className="space-y-4">
            {error && (
              <div className="rounded-md bg-red-50 p-4 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
                {error}
              </div>
            )}

            {questions.length > 0 && (
              <>
                <div className="flex items-center justify-between print:hidden">
                  <div className="flex items-center gap-3">
                    <h2 className="text-lg font-semibold">
                      생성된 문항 ({questions.length}개)
                    </h2>
                    {lastRequest && (
                      <Badge variant="secondary">
                        {GRADE_LABELS[lastRequest.grade_level]}
                      </Badge>
                    )}
                    {examSetId && (
                      <span className="text-xs text-muted-foreground">
                        Set: {examSetId}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowAllAnswers((p) => !p)}
                    >
                      {showAllAnswers ? "전체 정답 숨기기" : "전체 정답 보기"}
                    </Button>
                    {user && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setSaveDialogOpen(true)}
                      >
                        <Save className="mr-1.5 h-3.5 w-3.5" />
                        시험지 저장
                      </Button>
                    )}
                    <ExamExportDialog
                      questions={questions}
                      defaultGradeLevel={lastRequest?.grade_level}
                    />
                  </div>
                </div>

                <Separator className="print:hidden" />

                <div className="hidden print:block print:mb-6">
                  <h1 className="text-center text-xl font-bold">영어 시험</h1>
                  <p className="text-center text-sm text-gray-500">
                    {lastRequest
                      ? GRADE_LABELS[lastRequest.grade_level]
                      : ""}{" "}
                    | {questions.length}문항
                  </p>
                </div>

                <div className="space-y-4">
                  {questions.map((q, i) => (
                    <QuestionCard
                      key={q.id ?? i}
                      question={q}
                      index={i}
                      showAnswer={showAllAnswers}
                      onDelete={() => handleDelete(q.id, i)}
                    />
                  ))}
                </div>
              </>
            )}

            {questions.length === 0 && !isLoading && !error && (
              <div className="flex min-h-[400px] items-center justify-center rounded-lg border border-dashed">
                <div className="text-center">
                  <p className="text-lg font-medium text-muted-foreground">
                    왼쪽 폼에서 조건을 설정하고
                  </p>
                  <p className="text-lg font-medium text-muted-foreground">
                    &ldquo;문항 생성하기&rdquo; 버튼을 클릭하세요
                  </p>
                </div>
              </div>
            )}

            {isLoading && (
              <div className="flex min-h-[400px] items-center justify-center">
                <div className="text-center space-y-3">
                  <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                  <p className="text-muted-foreground">
                    DSPy 파이프라인으로 문항을 생성하고 있습니다...
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      <SaveExamDialog
        open={saveDialogOpen}
        onOpenChange={setSaveDialogOpen}
        questions={questions}
        gradeLevel={lastRequest?.grade_level}
      />
    </div>
  );
}
