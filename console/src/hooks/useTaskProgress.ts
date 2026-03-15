import { useEffect, useRef, useState } from 'react';
import { taskProgressClient, type TaskProgressEvent, type ProgressEventHandler } from '../api/websocket';

export interface TaskProgressState {
  status?: string;
  response?: string;
  error?: string;
  reason?: string;
  verified?: boolean;
  events: Array<{ type: string; timestamp: number; data: any }>;
}

/**
 * Hook to subscribe to task progress updates via WebSocket
 */
export function useTaskProgress(taskId: string | null): TaskProgressState {
  const [state, setState] = useState<TaskProgressState>({
    events: [],
  });

  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    if (!taskId) return;

    console.log('[useTaskProgress] Subscribing to task:', taskId);

    const handleProgress: ProgressEventHandler = (event: TaskProgressEvent) => {
      console.log('[useTaskProgress] Received event:', event);

      setState(prev => {
        const newEvents = [
          ...prev.events,
          {
            type: event.event.type,
            timestamp: Date.now(),
            data: event.event,
          },
        ];

        // Keep only last 50 events
        if (newEvents.length > 50) {
          newEvents.shift();
        }

        return {
          ...prev,
          status: event.event.status || prev.status,
          // Extract response from event data or from task object in status events
          response: event.event.response ||
                    (event.event.task?.llm_response) ||
                    prev.response,
          error: event.event.error || prev.error,
          reason: event.event.reason || prev.reason,
          verified: event.event.verified !== undefined
            ? event.event.verified
            : (event.event.task?.verification_result !== undefined
                ? event.event.task.verification_result
                : prev.verified),
          events: newEvents,
        };
      });
    };

    // Subscribe to task progress
    const unsubscribe = taskProgressClient.subscribe(taskId, handleProgress);

    // Cleanup on unmount or taskId change
    return () => {
      console.log('[useTaskProgress] Unsubscribing from task:', taskId);
      unsubscribe();
    };
  }, [taskId]);

  return state;
}
