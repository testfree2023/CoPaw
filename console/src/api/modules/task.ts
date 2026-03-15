/**
 * Task API module
 */
import { request } from '../request';
import type { TaskSpec, TaskListItem, TaskSummary, CreateTaskRequest } from '../types/task';

export type { TaskSpec, TaskListItem, TaskSummary, CreateTaskRequest };

export interface TaskTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  placeholders: string[];
}

export interface CreateTaskFromTemplateRequest {
  template_id: string;
  user_id: string;
  channel?: string;
  session_id: string;
  placeholder_values: Record<string, string>;
}

/**
 * Task API functions
 * Note: Use relative paths (without /api prefix) as request.ts adds /api automatically
 */
export const taskApi = {
  /**
   * Get list of tasks with optional filtering
   */
  listTasks: (params?: {
    status?: string;
    task_type?: string;
    user_id?: string;
    channel?: string;
    limit?: number;
  }) => {
    const queryParams = new URLSearchParams();
    if (params?.status) queryParams.append('status', params.status);
    if (params?.task_type) queryParams.append('task_type', params.task_type);
    if (params?.user_id) queryParams.append('user_id', params.user_id);
    if (params?.channel) queryParams.append('channel', params.channel);
    if (params?.limit) queryParams.append('limit', String(params.limit));

    return request<TaskListItem[]>(`/tasks${queryParams.toString() ? `?${queryParams.toString()}` : ''}`, {
      method: 'GET',
    });
  },

  /**
   * Get task details by ID
   */
  getTask: (taskId: string) => {
    return request<TaskSpec>(`/tasks/${taskId}`, {
      method: 'GET',
    });
  },

  /**
   * Retry a failed task
   */
  retryTask: (taskId: string) => {
    return request<{ status: string; message: string }>(`/tasks/${taskId}/retry`, {
      method: 'POST',
    });
  },

  /**
   * Manually verify a task
   */
  verifyTask: (taskId: string, success: boolean, details?: string) => {
    return request<{ status: string; message: string }>(`/tasks/${taskId}/verify`, {
      method: 'POST',
      body: JSON.stringify({ success, details }),
    });
  },

  /**
   * Create a new task
   */
  createTask: (task: CreateTaskRequest) => {
    return request<TaskSpec>('/tasks', {
      method: 'POST',
      body: JSON.stringify(task),
    });
  },

  /**
   * Delete a task
   */
  deleteTask: (taskId: string) => {
    return request<{ status: string; message: string }>(`/tasks/${taskId}`, {
      method: 'DELETE',
    });
  },

  /**
   * Get task statistics summary
   */
  getTaskSummary: () => {
    return request<TaskSummary>('/tasks/stats/summary', {
      method: 'GET',
    });
  },

  /**
   * Get list of available task templates
   */
  listTemplates: (category?: string) => {
    const url = category
      ? `/tasks/templates?category=${category}`
      : '/tasks/templates';
    return request<{ templates: TaskTemplate[] }>(url, {
      method: 'GET',
    });
  },

  /**
   * Create a task from template
   */
  createTaskFromTemplate: (req: CreateTaskFromTemplateRequest) => {
    return request<TaskSpec>('/tasks/from-template', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },
};
