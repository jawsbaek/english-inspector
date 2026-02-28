"use client";

import { Calendar, FileDown, FileText, Loader2, School } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ExamMetadata } from "@/lib/pdf-export";
import type { GradeLevel, Question } from "@/types/question";
import { GRADE_LABELS } from "@/types/question";

interface ExamExportDialogProps {
  questions: Question[];
  defaultGradeLevel?: GradeLevel;
  children?: React.ReactNode;
}

export default function ExamExportDialog({
  questions,
  defaultGradeLevel,
  children,
}: ExamExportDialogProps) {
  const today = new Date().toISOString().split("T")[0];

  const [open, setOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [includeAnswers, setIncludeAnswers] = useState(false);
  const [form, setForm] = useState<Omit<ExamMetadata, "includeAnswers">>({
    title: "영어 시험",
    schoolName: "",
    date: today,
    gradeLevel: defaultGradeLevel,
  });

  const handleChange = (field: keyof typeof form, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleExport = async () => {
    if (questions.length === 0) return;
    setIsExporting(true);
    try {
      const { exportExamToPDF } = await import("@/lib/pdf-export");
      await exportExamToPDF(questions, { ...form, includeAnswers });
    } catch (err) {
      console.error("PDF export failed:", err);
    } finally {
      setIsExporting(false);
    }
  };

  const gradeLabel = defaultGradeLevel ? GRADE_LABELS[defaultGradeLevel] : null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children ?? (
          <Button size="sm">
            <FileDown className="mr-1.5 h-3.5 w-3.5" />
            PDF 내보내기
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileDown className="h-4 w-4" />
            PDF 내보내기
          </DialogTitle>
          <DialogDescription>
            시험지 정보를 입력하고 PDF를 다운로드하세요.
            {gradeLabel && (
              <span className="ml-1 rounded bg-secondary px-1.5 py-0.5 text-xs font-medium text-secondary-foreground">
                {gradeLabel}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Exam Title */}
          <div className="space-y-1.5">
            <Label htmlFor="export-title" className="flex items-center gap-1.5 text-sm">
              <FileText className="h-3.5 w-3.5 text-muted-foreground" />
              시험 제목
            </Label>
            <Input
              id="export-title"
              value={form.title}
              onChange={(e) => handleChange("title", e.target.value)}
              placeholder="예: 1학기 중간고사"
            />
          </div>

          {/* School Name */}
          <div className="space-y-1.5">
            <Label htmlFor="export-school" className="flex items-center gap-1.5 text-sm">
              <School className="h-3.5 w-3.5 text-muted-foreground" />
              학교명
            </Label>
            <Input
              id="export-school"
              value={form.schoolName}
              onChange={(e) => handleChange("schoolName", e.target.value)}
              placeholder="예: 한국중학교"
            />
          </div>

          {/* Date */}
          <div className="space-y-1.5">
            <Label htmlFor="export-date" className="flex items-center gap-1.5 text-sm">
              <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
              시험 날짜
            </Label>
            <Input
              id="export-date"
              type="date"
              value={form.date}
              onChange={(e) => handleChange("date", e.target.value)}
            />
          </div>

          {/* Include Answers Toggle */}
          <div className="flex items-center justify-between rounded-lg border px-4 py-3">
            <div className="space-y-0.5">
              <p className="text-sm font-medium">정답 포함</p>
              <p className="text-xs text-muted-foreground">정답과 해설을 시험지에 포함합니다</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={includeAnswers}
              onClick={() => setIncludeAnswers((p) => !p)}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
                includeAnswers ? "bg-primary" : "bg-input"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform ${
                  includeAnswers ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Summary */}
          <div className="rounded-md bg-muted/50 px-4 py-3 text-xs text-muted-foreground">
            <p>
              총 <span className="font-semibold text-foreground">{questions.length}문항</span>이
              포함됩니다.
            </p>
            <p className="mt-0.5">정답 페이지는 항상 별도 페이지에 생성됩니다.</p>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => setOpen(false)} disabled={isExporting}>
            취소
          </Button>
          <Button
            onClick={handleExport}
            disabled={isExporting || questions.length === 0}
            className="min-w-[120px]"
          >
            {isExporting ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                생성 중...
              </>
            ) : (
              <>
                <FileDown className="mr-1.5 h-3.5 w-3.5" />
                PDF 다운로드
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
