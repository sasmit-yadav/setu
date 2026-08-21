import { useEffect, useRef } from "react";
import { getToken, opsSocketUrl } from "../lib/api";

export function useOpsSocket(onEvent: (payload?: Record<string, unknown>) => void) {
  const cb = useRef(onEvent);
  cb.current = onEvent;

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const socket = new WebSocket(opsSocketUrl(token));
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
