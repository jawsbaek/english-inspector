"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { Question } from "@/types/question";
import { QUESTION_TYPE_LABELS } from "@/types/question";

interface QuestionCardProps {
  question: Question;
  index: number;
  showAnswer: boolean;
  onToggleAnswer?: () => void;
  onDelete?: () => void;
}

export default function QuestionCard({
  question,
  index,
  showAnswer,
  onToggleAnswer,
  onDelete,
}: QuestionCardProps) {
  const [localShowAnswer, setLocalShowAnswer] = useState(showAnswer);

  useEffect(() => setLocalShowAnswer(showAnswer), [showAnswer]);

  const toggleAnswer = () => {
    setLocalShowAnswer((prev) => !prev);
    onToggleAnswer?.();
  };

  return (
    <Card className="relative">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold">Q{index + 1}.</span>
            <Badge variant="secondary">{QUESTION_TYPE_LABELS[question.question_type]}</Badge>
            <Badge variant="outline">난이도 {question.difficulty}</Badge>
          </div>
          {onDelete && (
            <Button
              variant="ghost"
              size="sm"
              className="text-red-500 hover:text-red-700"
              onClick={onDelete}
            >
              삭제
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {question.passage && (
          <div className="rounded-md bg-muted p-4 text-sm leading-relaxed">
            <p className="mb-1 font-semibold text-muted-foreground">[지문]</p>
            <p className="whitespace-pre-wrap">{question.passage}</p>
          </div>
        )}

        <p className="text-base font-medium leading-relaxed">{question.question_text}</p>

        {question.choices && question.choices.length > 0 && (
          <div className="space-y-1.5 pl-2">
            {question.choices.map((choice) => (
              <div
                key={choice.label}
                className={`rounded-md px-3 py-1.5 text-sm ${
                  localShowAnswer && choice.label === question.correct_answer
                    ? "bg-green-100 font-semibold text-green-800 dark:bg-green-900 dark:text-green-200"
                    : "bg-muted/50"
                }`}
              >
                <span className="font-medium">{choice.label}.</span> {choice.text}
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <Button variant="outline" size="sm" onClick={toggleAnswer}>
            {localShowAnswer ? "정답 숨기기" : "정답 보기"}
          </Button>
        </div>

        {localShowAnswer && (
          <>
            <Separator />
            <div className="space-y-1.5 text-sm">
              <p>
                <span className="font-semibold text-green-700 dark:text-green-400">정답:</span>{" "}
                {question.correct_answer}
              </p>
              {question.explanation && (
                <p>
                  <span className="font-semibold text-blue-700 dark:text-blue-400">해설:</span>{" "}
                  {question.explanation}
                </p>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
