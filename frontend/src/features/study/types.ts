// 학습 도메인 Zod 스키마 — 백엔드 응답 런타임 검증용.

import { z } from "zod";

export const StudyStatsSchema = z.object({
  due_today: z.number().int().min(0),
  new_available: z.number().int().min(0),
  weak_tags: z.array(z.string()),
});

export const ProblemOutSchema = z.object({
  problem_id: z.string().uuid(),
  content_item_id: z.string().uuid(),
  // 백엔드 ProblemType 열거값(소문자)과 동일하게 유지
  problem_type: z.enum(["mcq_meaning", "mcq_reading", "fill_blank", "short_answer", "translation", "listening"]),
  prompt: z.string(),
  answer: z.string(),
  distractors: z.array(z.string()),
  tags: z.array(z.string()),
});

export const StudySessionSchema = z.object({
  id: z.string().uuid(),
  date: z.string(),
  problems: z.array(ProblemOutSchema),
  completed_count: z.number().int().min(0),
  total_count: z.number().int().min(0),
  started_at: z.string(),
});

export const AttemptResultSchema = z.object({
  id: z.string().uuid(),
  correct: z.boolean(),
  rating: z.string().nullable(),
  next_due_at: z.string(),
  created_at: z.string(),
});

export type StudyStats = z.infer<typeof StudyStatsSchema>;
export type ProblemOut = z.infer<typeof ProblemOutSchema>;
export type StudySession = z.infer<typeof StudySessionSchema>;
export type AttemptResult = z.infer<typeof AttemptResultSchema>;
