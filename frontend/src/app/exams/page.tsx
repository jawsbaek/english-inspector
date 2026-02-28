"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, BookOpen, Calendar, Hash, ChevronLeft } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { listExams, deleteExam } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import type { ExamSet } from "@/types/auth";
import { GRADE_LABELS } from "@/types/question";
import type { GradeLevel } from "@/types/question";

export default function ExamsPage() {
  const router = useRouter();
  const [exams, setExams] = useState<ExamSet[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listExams();
      setExams(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "시험지 목록을 불러오지 못했습니다."
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/");
      return;
    }
    load();
  }, [load, router]);

  const handleDelete = async (id: number) => {
    if (!confirm("이 시험지를 삭제하시겠습니까?")) return;
    setDeletingId(id);
    try {
      await deleteExam(id);
      setExams((prev) => prev.filter((e) => e.id !== id));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "삭제에 실패했습니다."
      );
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  const gradeLabel = (level: string) =>
    GRADE_LABELS[level as GradeLevel] ?? level;

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="container mx-auto flex items-center justify-between px-4 py-4">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push("/")}
              className="gap-1.5"
            >
              <ChevronLeft className="h-4 w-4" />
              홈으로
            </Button>
            <Separator orientation="vertical" className="h-5" />
            <div>
              <h1 className="text-xl font-bold flex items-center gap-2">
                <BookOpen className="h-5 w-5" />
                내 시험지
              </h1>
              <p className="text-xs text-muted-foreground">
                저장된 시험 문항 세트
              </p>
            </div>
          </div>

          <Button
            size="sm"
            onClick={() => router.push("/")}
            className="gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" />
            새 시험지 만들기
          </Button>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {isLoading && (
          <div className="flex min-h-[300px] items-center justify-center">
            <div className="text-center space-y-3">
              <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              <p className="text-sm text-muted-foreground">불러오는 중...</p>
            </div>
          </div>
        )}

        {!isLoading && exams.length === 0 && !error && (
          <div className="flex min-h-[300px] items-center justify-center rounded-lg border border-dashed">
            <div className="text-center space-y-3">
              <BookOpen className="mx-auto h-10 w-10 text-muted-foreground/50" />
              <p className="font-medium text-muted-foreground">
                저장된 시험지가 없습니다
              </p>
              <Button size="sm" onClick={() => router.push("/")}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                문항 생성하러 가기
              </Button>
            </div>
          </div>
        )}

        {!isLoading && exams.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {exams.map((exam) => (
              <Card
                key={exam.id}
                className="relative transition-shadow hover:shadow-md"
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base leading-snug line-clamp-2">
                      {exam.title}
                    </CardTitle>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 shrink-0 p-0 text-muted-foreground hover:text-destructive"
                      onClick={() => handleDelete(exam.id)}
                      disabled={deletingId === exam.id}
                      aria-label="시험지 삭제"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary" className="text-xs">
                      {gradeLabel(exam.grade_level)}
                    </Badge>
                  </div>

                  <div className="space-y-1.5 text-xs text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <Hash className="h-3 w-3" />
                      <span>{exam.question_count}문항</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Calendar className="h-3 w-3" />
                      <span>{formatDate(exam.created_at)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
