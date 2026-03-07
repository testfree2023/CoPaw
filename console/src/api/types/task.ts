/**
 * Task types for CoPaw task management
 */

export type TaskType = 'instruction' | 'rule' | 'conversation';

export type TaskStatus =
  | 'pending'
  | 'processing'
  | 'waiting_verification'
  | 'completed'
  | 'failed'
  | 'reprocessing';

export interface TaskSpec {
  id: string;
  user_id: string;
  channel: string;
  session_id: string;
  type: TaskType;
  query: string;
  status: TaskStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  llm_response?: string;
  verification_result?: boolean;
  verification_details?: string;
  retry_count: number;
  max_retries: number;
  last_error?: string;
  metadata?: Record<string, unknown>;
}

export interface TaskListItem {
  id: string;
  user_id: string;
  channel: string;
  session_id: string;
  type: TaskType;
  query: string;
  status: TaskStatus;
  created_at: string;
  completed_at?: string;
  verification_result?: boolean;
}

export interface TaskSummary {
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
}

export interface CreateTaskRequest {
  user_id: string;
  channel?: string;
  session_id: string;
  query: string;
  task_type?: TaskType;
  metadata?: Record<string, unknown>;
}
