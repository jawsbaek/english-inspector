import type { Question } from "@/types/question";
import { GRADE_LABELS } from "@/types/question";

export interface ExamMetadata {
  title: string;
  schoolName: string;
  date: string;
  gradeLevel?: string;
  includeAnswers: boolean;
}

// jsPDF is loaded client-side only
async function getJsPDF() {
  const { default: jsPDF } = await import("jspdf");
  return jsPDF;
}

// Wrap text to fit within a given width (in points), returns array of lines
function wrapText(
  text: string,
  maxWidth: number,
  doc: InstanceType<Awaited<ReturnType<typeof getJsPDF>>>
): string[] {
  if (!text) return [""];
  const words = text.split(" ");
  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    const test = current ? `${current} ${word}` : word;
    if (doc.getTextWidth(test) > maxWidth) {
      if (current) lines.push(current);
      current = word;
    } else {
      current = test;
    }
  }
  if (current) lines.push(current);
  return lines.length > 0 ? lines : [""];
}

// Wrap Korean/mixed text that can break at any character boundary
function wrapMixed(
  text: string,
  maxWidth: number,
  doc: InstanceType<Awaited<ReturnType<typeof getJsPDF>>>
): string[] {
  if (!text) return [""];
  const lines: string[] = [];
  let current = "";

  for (const ch of text) {
    if (ch === "\n") {
      lines.push(current);
      current = "";
      continue;
    }
    const test = current + ch;
    if (doc.getTextWidth(test) > maxWidth) {
      lines.push(current);
      current = ch;
    } else {
      current = test;
    }
  }
  if (current) lines.push(current);
  return lines.length > 0 ? lines : [""];
}

export async function exportExamToPDF(
  questions: Question[],
  metadata: ExamMetadata
): Promise<void> {
  const JsPDF = await getJsPDF();

  const doc = new JsPDF({
    orientation: "portrait",
    unit: "pt",
    format: "a4",
  });

  // ── Page geometry ────────────────────────────────────────────
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const marginL = 56;
  const marginR = 56;
  const marginT = 60;
  const marginB = 60;
  const contentW = pageW - marginL - marginR;

  let y = marginT;

  // ── Helper: add a new page and reset y ──────────────────────
  const newPage = () => {
    doc.addPage();
    y = marginT;
  };

  // ── Helper: check remaining space; break page if needed ─────
  const ensureSpace = (needed: number) => {
    if (y + needed > pageH - marginB) newPage();
  };

  // ── Helper: draw a thin rule ─────────────────────────────────
  const rule = (thickness = 0.5, color: [number, number, number] = [180, 180, 180]) => {
    doc.setDrawColor(...color);
    doc.setLineWidth(thickness);
    doc.line(marginL, y, pageW - marginR, y);
    y += 6;
  };

  // ── Helper: print a text block and advance y ─────────────────
  const printBlock = (
    lines: string[],
    lineHeight: number,
    x = marginL
  ) => {
    for (const line of lines) {
      ensureSpace(lineHeight);
      doc.text(line, x, y);
      y += lineHeight;
    }
  };

  // ════════════════════════════════════════════════════════════
  // HEADER
  // ════════════════════════════════════════════════════════════

  // School name — centered, bold
  doc.setFont("helvetica", "bold");
  doc.setFontSize(15);
  doc.setTextColor(30, 30, 30);
  doc.text(metadata.schoolName || "학교", pageW / 2, y, { align: "center" });
  y += 22;

  // Exam title — centered, larger bold
  doc.setFontSize(20);
  doc.text(metadata.title || "영어 시험", pageW / 2, y, { align: "center" });
  y += 10;

  // Thick rule under title
  doc.setDrawColor(30, 30, 30);
  doc.setLineWidth(1.5);
  doc.line(marginL, y, pageW - marginR, y);
  y += 12;

  // Date + grade row
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(90, 90, 90);
  const gradeLabel = metadata.gradeLevel
    ? GRADE_LABELS[metadata.gradeLevel as keyof typeof GRADE_LABELS] ?? ""
    : "";
  doc.text(`날짜: ${metadata.date}`, marginL, y);
  if (gradeLabel) doc.text(`학년: ${gradeLabel}`, pageW / 2, y, { align: "center" });
  doc.text(`총 ${questions.length}문항`, pageW - marginR, y, { align: "right" });
  y += 18;

  // Student info boxes
  doc.setDrawColor(140, 140, 140);
  doc.setLineWidth(0.5);
  const boxY = y;
  const boxH = 20;
  // "이름:" label + underline box
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(40, 40, 40);
  doc.text("이름:", marginL, boxY + 13);
  doc.rect(marginL + 28, boxY + 2, 90, boxH - 2);
  doc.text("반:", marginL + 140, boxY + 13);
  doc.rect(marginL + 158, boxY + 2, 60, boxH - 2);
  doc.text("번호:", marginL + 238, boxY + 13);
  doc.rect(marginL + 262, boxY + 2, 50, boxH - 2);
  y = boxY + boxH + 14;

  // Light rule
  rule(0.5, [200, 200, 200]);
  y += 4;

  // ════════════════════════════════════════════════════════════
  // QUESTIONS
  // ════════════════════════════════════════════════════════════

  for (let i = 0; i < questions.length; i++) {
    const q = questions[i];

    ensureSpace(40);

    // ── Question number badge area ──────────────────────────
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.setTextColor(255, 255, 255);
    doc.setFillColor(40, 40, 40);
    const badgeW = 22;
    const badgeH = 14;
    const badgeX = marginL;
    doc.roundedRect(badgeX, y - 10, badgeW, badgeH, 2, 2, "F");
    doc.text(`${i + 1}`, badgeX + badgeW / 2, y, { align: "center" });

    // Question type label
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(100, 100, 100);
    const typeKo: Record<string, string> = {
      multiple_choice: "[객관식]",
      fill_in_blank: "[빈칸]",
      reading_comprehension: "[독해]",
      grammar: "[문법]",
      vocabulary: "[어휘]",
      short_answer: "[주관식]",
    };
    doc.text(typeKo[q.question_type] ?? "", badgeX + badgeW + 5, y);

    // Difficulty dots
    const diffX = pageW - marginR;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(140, 140, 140);
    doc.text(`난이도 ${"●".repeat(q.difficulty)}${"○".repeat(5 - q.difficulty)}`, diffX, y, { align: "right" });

    y += 6;

    // ── Passage block (reading comprehension) ───────────────
    if (q.passage) {
      ensureSpace(20);
      const passageIndent = marginL + 4;
      const passageW = contentW - 8;

      // Passage box background
      const passageLines = wrapMixed(q.passage, passageW - 16, doc);
      const passageBlockH = passageLines.length * 12 + 20;
      ensureSpace(passageBlockH);

      doc.setFillColor(247, 247, 247);
      doc.setDrawColor(210, 210, 210);
      doc.setLineWidth(0.5);
      doc.roundedRect(passageIndent, y, passageW, passageBlockH, 3, 3, "FD");

      y += 8;
      doc.setFont("helvetica", "bold");
      doc.setFontSize(8);
      doc.setTextColor(100, 100, 100);
      doc.text("[지문]", passageIndent + 8, y);
      y += 12;

      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      doc.setTextColor(40, 40, 40);
      for (const line of passageLines) {
        ensureSpace(12);
        doc.text(line, passageIndent + 8, y);
        y += 12;
      }
      y += 8;
    }

    // ── Question text ────────────────────────────────────────
    const qIndent = marginL + 28;
    const qWidth = contentW - 28;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(20, 20, 20);
    const qLines = wrapMixed(q.question_text, qWidth, doc);
    for (const line of qLines) {
      ensureSpace(14);
      doc.text(line, qIndent, y);
      y += 14;
    }
    y += 3;

    // ── Choices ──────────────────────────────────────────────
    if (q.choices && q.choices.length > 0) {
      const choiceIndent = qIndent + 8;
      const choiceW = qWidth - 8;
      doc.setFontSize(9.5);

      for (const choice of q.choices) {
        const choiceText = `${choice.label}.  ${choice.text}`;
        const choiceLines = wrapMixed(choiceText, choiceW, doc);
        const lineH = 13;
        const blockH = choiceLines.length * lineH + 4;
        ensureSpace(blockH);

        // Highlight correct answer when includeAnswers is true
        if (metadata.includeAnswers && choice.label === q.correct_answer) {
          doc.setFillColor(220, 245, 220);
          doc.roundedRect(choiceIndent - 2, y - 10, choiceW + 4, blockH, 2, 2, "F");
        }

        doc.setFont("helvetica", "bold");
        doc.setTextColor(50, 50, 50);
        doc.text(`${choice.label}.`, choiceIndent, y);

        doc.setFont("helvetica", "normal");
        doc.setTextColor(30, 30, 30);
        const firstLine = choiceLines[0].replace(/^[A-Z]\.\s*/, "");
        doc.text(firstLine, choiceIndent + 16, y);
        y += lineH;
        for (let ci = 1; ci < choiceLines.length; ci++) {
          ensureSpace(lineH);
          doc.text(choiceLines[ci], choiceIndent + 16, y);
          y += lineH;
        }
      }
      y += 4;
    }

    // ── Fill-in-blank answer line ────────────────────────────
    if (q.question_type === "fill_in_blank" || q.question_type === "short_answer") {
      ensureSpace(22);
      doc.setDrawColor(160, 160, 160);
      doc.setLineWidth(0.5);
      doc.line(qIndent, y + 10, qIndent + 160, y + 10);
      y += 20;
    }

    // ── Explanation (only when includeAnswers) ───────────────
    if (metadata.includeAnswers && q.explanation) {
      ensureSpace(16);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(8);
      doc.setTextColor(80, 120, 200);
      const expPrefix = "해설: ";
      const expLines = wrapMixed(expPrefix + q.explanation, qWidth + 10, doc);
      for (const line of expLines) {
        ensureSpace(11);
        doc.text(line, qIndent, y);
        y += 11;
      }
      y += 2;
    }

    // Divider between questions
    y += 6;
    if (i < questions.length - 1) {
      rule(0.3, [220, 220, 220]);
      y += 2;
    }
  }

  // ════════════════════════════════════════════════════════════
  // ANSWER SHEET (separate page)
  // ════════════════════════════════════════════════════════════
  newPage();

  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.setTextColor(30, 30, 30);
  doc.text("정답 및 해설", pageW / 2, y, { align: "center" });
  y += 6;

  doc.setDrawColor(30, 30, 30);
  doc.setLineWidth(1.2);
  doc.line(marginL, y, pageW - marginR, y);
  y += 16;

  // Build answer table
  const colW = (contentW - 16) / 4;
  const rowH = 22;

  for (let i = 0; i < questions.length; i++) {
    const col = i % 4;
    if (col === 0) {
      ensureSpace(rowH + 4);
      if (i !== 0) y += 4;
    }

    const q = questions[i];
    const cellX = marginL + 8 + col * (colW + 4);

    // Cell background alternating
    doc.setFillColor(col % 2 === 0 ? 248 : 242, 248, 255);
    doc.setDrawColor(210, 220, 230);
    doc.setLineWidth(0.4);
    doc.roundedRect(cellX, y - rowH + 6, colW, rowH, 2, 2, "FD");

    // Question number
    doc.setFont("helvetica", "bold");
    doc.setFontSize(8);
    doc.setTextColor(80, 100, 140);
    doc.text(`${i + 1}.`, cellX + 5, y - 4);

    // Answer
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.setTextColor(20, 80, 160);
    doc.text(q.correct_answer, cellX + colW / 2, y - 4, { align: "center" });

    if (col === 3 || i === questions.length - 1) {
      y += rowH;
    }
  }

  y += 16;
  rule(0.4, [200, 210, 220]);

  // Explanations section
  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.setTextColor(40, 40, 40);
  doc.text("문제 해설", marginL, y);
  y += 14;

  for (let i = 0; i < questions.length; i++) {
    const q = questions[i];
    if (!q.explanation) continue;

    ensureSpace(28);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);
    doc.setTextColor(20, 20, 20);
    doc.text(`${i + 1}번`, marginL, y);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);
    doc.setTextColor(20, 120, 60);
    doc.text(`정답: ${q.correct_answer}`, marginL + 28, y);
    y += 12;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);
    doc.setTextColor(50, 50, 50);
    const expLines = wrapMixed(q.explanation, contentW - 10, doc);
    for (const line of expLines) {
      ensureSpace(12);
      doc.text(line, marginL + 8, y);
      y += 12;
    }
    y += 4;
  }

  // ── Page numbers ────────────────────────────────────────────
  const totalPages = (doc.internal as unknown as { getNumberOfPages: () => number }).getNumberOfPages();
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(160, 160, 160);
    doc.text(`${p} / ${totalPages}`, pageW / 2, pageH - 24, { align: "center" });
    doc.text(metadata.title || "영어 시험", marginL, pageH - 24);
    doc.text(metadata.date, pageW - marginR, pageH - 24, { align: "right" });
  }

  // ── Save ─────────────────────────────────────────────────────
  const safeTitle = (metadata.title || "exam").replace(/\s+/g, "_");
  doc.save(`${safeTitle}_${metadata.date}.pdf`);
}
