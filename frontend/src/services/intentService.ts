import { api } from './api';

export interface IntentDetectRequest {
  original_intent: string;
  current_message: string;
  threshold?: number;
}

export interface IntentDetectResponse {
  original_keywords: string[];
  current_keywords: string[];
  drift_score: number;
  is_drifted: boolean;
  threshold: number;
}

export const intentService = {
  /** 检测意图飘移 */
  detect: (data: IntentDetectRequest) =>
    api.post<IntentDetectResponse>('/intent/detect', data),
};
