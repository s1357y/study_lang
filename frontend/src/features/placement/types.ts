// 배치 시험 도메인 Zod 스키마

import { z } from "zod";

export const PlacementProblemSchema = z.object({
  problem_id: z.string().uuid(),
  content_item_id: z.string().uuid(),
  problem_type: z.string(),
  prompt: z.string(),
  answer: z.string(),
  distractors: z.array(z.string()),
  tags: z.array(z.string()),
});

export const PlacementProblemsResponseSchema = z.object({
  problems: z.array(PlacementProblemSchema),
  total: z.number().int().min(0),
  placement_token: z.string(),
});

export const PlacementResultSchema = z.object({
  assigned_level: z.string(),
  level_label: z.string(),
  message: z.string(),
});

export type PlacementProblem = z.infer<typeof PlacementProblemSchema>;
export type PlacementProblemsResponse = z.infer<typeof PlacementProblemsResponseSchema>;
export type PlacementResult = z.infer<typeof PlacementResultSchema>;
