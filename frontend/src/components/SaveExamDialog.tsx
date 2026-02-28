"use client";

import { Loader2, Save } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createExam } from "@/lib/api";
import type { GradeLevel, Question } from "@/types/question";
import { GRADE_LABELS } from "@/types/question";

interface SaveExamDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  questions: Question[];
  gradeLevel?: GradeLevel;
  onSaved?: () => void;
}

export default function SaveExamDialog({
  open,
  onOpenChange,
  questions,
  gradeLevel,
  onSaved,
}: SaveExamDialogProps) {
  const [title, setTitle] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setError(null);
    setIsSaving(true);
    try {
      const questionIds = questions.map((q) => q.id).filter((id): id is number => id !== undefined);
      await createExam({
        title: title.trim(),
        grade_level: gradeLevel ?? "middle",
        question_ids: questionIds,
      });
      setSaved(true);
      onSaved?.();
      setTimeout(() => {
        onOpenChange(false);
        setSaved(false);
        setTitle("");
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장에 실패했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleOpenChange = (v: boolean) => {
    if (!isSaving) {
      onOpenChange(v);
      if (!v) {
        setError(null);
        setSaved(false);
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[380px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Save className="h-4 w-4" />
            시험지 저장
          </DialogTitle>
        </DialogHeader>

        {saved ? (
          <div className="py-6 text-center">
            <p className="text-sm font-medium text-green-700 dark:text-green-400">
              시험지가 저장되었습니다.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSave} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="exam-title">시험지 제목</Label>
              <Input
                id="exam-title"
                placeholder="예: 1학기 중간고사 영어"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                disabled={isSaving}
                autoFocus
              />
            </div>

            <div className="rounded-md bg-muted/50 px-3 py-2.5 text-xs text-muted-foreground space-y-0.5">
              <p>
                문항 수: <span className="font-semibold text-foreground">{questions.length}개</span>
              </p>
              {gradeLevel && (
                <p>
                  학년 수준:{" "}
                  <span className="font-semibold text-foreground">{GRADE_LABELS[gradeLevel]}</span>
                </p>
              )}
            </div>

            {error && (
              <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            )}

            <DialogFooter className="gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={isSaving}
              >
                취소
              </Button>
              <Button type="submit" disabled={isSaving || !title.trim()} className="min-w-[80px]">
                {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : "저장"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
