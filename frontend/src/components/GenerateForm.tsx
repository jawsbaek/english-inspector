"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { GenerateRequest, GradeLevel, QuestionType } from "@/types/question";
import { GRADE_LABELS, QUESTION_TYPE_LABELS } from "@/types/question";

interface GenerateFormProps {
  onGenerate: (req: GenerateRequest) => void;
  isLoading: boolean;
}

export default function GenerateForm({ onGenerate, isLoading }: GenerateFormProps) {
  const [gradeLevel, setGradeLevel] = useState<GradeLevel>("middle");
  const [selectedTypes, setSelectedTypes] = useState<QuestionType[]>(["multiple_choice"]);
  const [topic, setTopic] = useState("general");
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState(3);

  const toggleType = (type: QuestionType) => {
    setSelectedTypes((prev) =>
      prev.includes(type)
        ? prev.length > 1
          ? prev.filter((t) => t !== type)
          : prev
        : [...prev, type]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onGenerate({
      grade_level: gradeLevel,
      question_types: selectedTypes,
      topic,
      count,
      difficulty,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>시험 문항 생성</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label>학년 수준</Label>
            <Select value={gradeLevel} onValueChange={(v) => setGradeLevel(v as GradeLevel)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(GRADE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>문제 유형 (복수 선택 가능)</Label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(QUESTION_TYPE_LABELS).map(([value, label]) => (
                <Badge
                  key={value}
                  variant={selectedTypes.includes(value as QuestionType) ? "default" : "outline"}
                  className="cursor-pointer select-none"
                  onClick={() => toggleType(value as QuestionType)}
                >
                  {label}
                </Badge>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="topic">주제 / 토픽</Label>
            <Input
              id="topic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="예: 여행, 학교생활, 환경 등"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="count">문항 수</Label>
              <Input
                id="count"
                type="number"
                min={1}
                max={30}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label>난이도</Label>
              <Select value={String(difficulty)} onValueChange={(v) => setDifficulty(Number(v))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 - 매우 쉬움</SelectItem>
                  <SelectItem value="2">2 - 쉬움</SelectItem>
                  <SelectItem value="3">3 - 보통</SelectItem>
                  <SelectItem value="4">4 - 어려움</SelectItem>
                  <SelectItem value="5">5 - 매우 어려움</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "생성 중..." : "문항 생성하기"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
