import { useEffect, useRef } from "react";
import { getToken } from "../lib/api";

export function useOpsSocket(onEvent: (payload?: Record<string, unknown>) => void) {
  const cb = useRef(onEvent);
  cb.current = onEvent;

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(
      `${protocol}://${window.location.host}/api/v1/ws/ops?token=${encodeURIComponent(token)}`,
    );
    socket.onmessage = (event) => {
      try {
        cb.current(JSON.parse(String(event.data)) as Record<string, unknown>);
      } catch {
        cb.current();
      }
    };
    return () => socket.close();
  }, []);
}
