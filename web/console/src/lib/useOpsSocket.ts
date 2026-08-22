import { useEffect, useRef, useState } from "react";
import { getToken, opsSocketUrl } from "./api";

export type LinkState = "connecting" | "live" | "down";

export function useOpsSocket(onEvent: (payload?: Record<string, unknown>) => void): LinkState {
  const cb = useRef(onEvent);
  cb.current = onEvent;
  const [state, setState] = useState<LinkState>("connecting");

  useEffect(() => {
    let stopped = false;
    let socket: WebSocket | null = null;
    let retry = 0;

    function connect() {
      if (stopped) return;
      const token = getToken();
      if (!token) {
        setState("down");
        return;
      }
      setState("connecting");
      socket = new WebSocket(opsSocketUrl(token));
      socket.onopen = () => {
        if (!stopped) setState("live");
      };
      socket.onmessage = (event) => {
        try {
          cb.current(JSON.parse(String(event.data)) as Record<string, unknown>);
        } catch {
          cb.current();
        }
      };
      socket.onerror = () => {
        /* onclose follows */
      };
      socket.onclose = () => {
        if (stopped) return;
        setState("down");
        retry = window.setTimeout(connect, 4000);
      };
    }

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retry);
      socket?.close();
    };
  }, []);

  return state;
}
