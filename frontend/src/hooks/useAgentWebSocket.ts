import { useEffect, useRef, useState } from 'react';

type LogMessage = {
    type: 'log';
    content: string;
};

type AgentMessage = {
    type: 'agent_message';
    sender: string;
    content: string;
    timestamp?: string;
};

type SlideUpdate = {
    type: 'slide_update';
    code: string;
};

type ProgressData = {
    type: 'progress';
    current_step: number;
    total_steps: number;
    current_sub: number;
    total_subs: number;
    percent: number;
    next_agent: string;
};

type WebSocketMessage = LogMessage | SlideUpdate | AgentMessage | ProgressData;

export function useAgentWebSocket(url: string, threadId: string) {
    const ws = useRef<WebSocket | null>(null);
    const [logs, setLogs] = useState<string[]>([]);
    const [dialogue, setDialogue] = useState<AgentMessage[]>([]);
    const [currentSlideCode, setCurrentSlideCode] = useState<string | null>(null);
    const [progress, setProgress] = useState<ProgressData | null>(null);
    const [isConnected, setIsConnected] = useState(false);

    const reconnectTimerRef = useRef<any>(null);
    const pingIntervalRef = useRef<any>(null);
    const intentionalCloseRef = useRef(false);   // true = we closed on purpose (cleanup)
    const historyLoadedRef = useRef<string>('');

    // Load dialogue history from backend on thread change
    useEffect(() => {
        if (!threadId || historyLoadedRef.current === threadId) return;

        const loadHistory = async () => {
            try {
                const res = await fetch(`/api/dialogue/history/${threadId}`);
                const data = await res.json();
                if (data.dialogue && data.dialogue.length > 0) {
                    setDialogue(data.dialogue);
                    console.log(`📜 Loaded ${data.dialogue.length} dialogue messages from history.`);
                } else {
                    setDialogue([]);
                }
                historyLoadedRef.current = threadId;
            } catch (err) {
                console.error('Failed to load dialogue history:', err);
                setDialogue([]);
            }
        };

        loadHistory();
    }, [threadId]);

    useEffect(() => {
        if (!threadId) return;

        intentionalCloseRef.current = false;

        const connect = () => {
            // Guard: don't open a second socket if one is already open/connecting
            if (ws.current &&
                (ws.current.readyState === WebSocket.OPEN ||
                 ws.current.readyState === WebSocket.CONNECTING)) {
                return;
            }

            const wsUrl = `${url}/${threadId}`;
            console.log(`Connecting to session: ${threadId}`);
            const socket = new WebSocket(wsUrl);
            ws.current = socket;

            socket.onopen = () => {
                console.log('Connected to Agent Stream');
                setIsConnected(true);
                if (reconnectTimerRef.current) {
                    clearTimeout(reconnectTimerRef.current);
                    reconnectTimerRef.current = null;
                }
                setLogs((prev) => [...prev, `[System] Connected to Session: ${threadId}`]);
            };

            socket.onmessage = (event) => {
                try {
                    const data: WebSocketMessage = JSON.parse(event.data);

                    if (data.type === 'log') {
                        setLogs((prev) => [...prev, `[Agent] ${data.content}`]);
                    } else if (data.type === 'slide_update') {
                        setLogs((prev) => [...prev, '[System] Hot-Reloading Slide...']);
                        setCurrentSlideCode(data.code);
                    } else if (data.type === 'agent_message') {
                        setDialogue((prev) => [...prev, data]);
                        setLogs((prev) => [...prev, `[${data.sender}] ${data.content.substring(0, 50)}...`]);
                    } else if (data.type === 'progress') {
                        setProgress(data as ProgressData);
                    }
                    // 'pong' messages are ignored (keep-alive ack)
                } catch (err) {
                    console.error('Failed to parse WS message', err);
                }
            };

            socket.onclose = () => {
                setIsConnected(false);

                // If WE closed it (thread switch / unmount), do NOT reconnect.
                if (intentionalCloseRef.current) {
                    return;
                }

                setLogs((prev) => [...prev, '[System] Disconnected. Reconnecting in 3s...']);

                // Schedule a single reconnect attempt (idempotent)
                if (!reconnectTimerRef.current) {
                    reconnectTimerRef.current = setTimeout(() => {
                        reconnectTimerRef.current = null;
                        connect();   // direct reconnect — does NOT re-run the effect
                    }, 3000);
                }
            };

            socket.onerror = () => {
                // Let onclose handle the reconnect; just close cleanly.
                try { socket.close(); } catch { /* noop */ }
            };
        };

        connect();

        // --- Keep-Alive Ping Interval (20s) ---
        pingIntervalRef.current = setInterval(() => {
            if (ws.current && ws.current.readyState === WebSocket.OPEN) {
                ws.current.send(JSON.stringify({ type: 'ping', content: 'keep-alive' }));
            }
        }, 20000);

        // Cleanup: only runs on thread change or unmount (NOT on reconnect)
        return () => {
            intentionalCloseRef.current = true;
            if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
            if (reconnectTimerRef.current) {
                clearTimeout(reconnectTimerRef.current);
                reconnectTimerRef.current = null;
            }
            if (ws.current) {
                ws.current.onclose = null;  // prevent reconnect from firing on intentional close
                ws.current.close();
                ws.current = null;
            }
        };
    }, [url, threadId]);   // ← reconnectCount removed: connection no longer tears down on reconnect

    const sendMessage = (text: string, searchOptions?: any, projectId?: string) => {
        if (!ws.current || ws.current.readyState !== WebSocket.OPEN) return;

        const payload: any = {
            type: 'message',
            content: text,
            search_options: searchOptions || {}
        };
        if (projectId) {
            payload.project_id = projectId;
        }

        ws.current.send(JSON.stringify(payload));
        setLogs((prev) => [...prev, `[User] ${text}`]);
    };

    const sendCommand = (command: string) => {
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            const payload = JSON.stringify({ type: 'command', content: command });
            ws.current.send(payload);
            setLogs((prev) => [...prev, `[Command] Executing: ${command.toUpperCase()}`]);
        }
    };

    return { logs, dialogue, currentSlideCode, progress, sendMessage, sendCommand, isConnected };
}
