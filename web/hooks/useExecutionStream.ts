'use client';
import { useEffect } from 'react';
import { API } from '../lib/api';
import type { RunStatus } from '../lib/api';

/** SSE provides readable observable execution events; polling remains a fallback. */
export function useExecutionStream(
  enabled: boolean,
  onStatus: (value: RunStatus, logDelta: string, replaceLog: boolean) => void,
) {
  useEffect(() => {
    if (!enabled || typeof EventSource === 'undefined') return;
    const stream = new EventSource(`${API}/api/experiment/log/stream`);
    const handleExecution = (event: MessageEvent) => {
      try {
        const packet = JSON.parse(event.data) as {
          state: RunStatus;
          log_delta?: string;
          replace_log?: boolean;
        };
        if (packet.state && typeof packet.state.status === 'string') {
          onStatus(packet.state, packet.log_delta || '', Boolean(packet.replace_log));
        }
      } catch {
        // Invalid event packets do not become model results; status polling continues.
      }
    };
    const handleTerminal = () => stream.close();
    stream.addEventListener('execution', handleExecution as EventListener);
    stream.addEventListener('terminal', handleTerminal);
    return () => stream.close();
  }, [enabled, onStatus]);
}
