import { useEffect, useState } from "react";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface StreamEvent {
  event: string;
  data: any;
  timestamp?: string;
}

export function useRunStream(runId: string | null) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [latestEvent, setLatestEvent] = useState<StreamEvent | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setIsConnected(false);
      return;
    }

    const eventSource = new EventSource(`${BASE_URL}/api/v1/runs/${runId}/events`);

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    eventSource.onmessage = (message) => {
      try {
        const parsedData = JSON.parse(message.data);
        const newEvent: StreamEvent = {
          event: message.type || "message",
          data: parsedData,
          timestamp: new Date().toISOString(),
        };

        setLatestEvent(newEvent);
        setEvents((prev) => [...prev, newEvent]);
      } catch (e) {
        console.error("Failed to parse SSE event data:", e);
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE Connection Error:", err);
      setError("Lost connection to live run stream.");
      setIsConnected(false);
      eventSource.close();
    };

    return () => {
      eventSource.close();
      setIsConnected(false);
    };
  }, [runId]);

  return { events, latestEvent, isConnected, error };
}