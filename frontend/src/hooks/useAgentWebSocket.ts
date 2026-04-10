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
    const [reconnectCount, setReconnectCount] = useState(0);
    const reconnectTimerRef = useRef<any>(null);
    const historyLoadedRef = useRef<string>(''); // Track which threadId's history was loaded

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

    const connect = () => {
        if (!threadId) return;

        const wsUrl = `${url}/${threadId}`;
        console.log(`Connecting to session: ${threadId} (Attempt: ${reconnectCount + 1})`);

        ws.current = new WebSocket(wsUrl);

        ws.current.onopen = () => {
            console.log('Connected to Agent Stream');
            setIsConnected(true);
            setReconnectCount(0); // Reset on success
            if (reconnectTimerRef.current) {
                clearTimeout(reconnectTimerRef.current);
                reconnectTimerRef.current = null;
            }
            setLogs((prev) => [...prev, `[System] Connected to Session: ${threadId}`]);
        };

        ws.current.onmessage = (event) => {
            try {
                const data: WebSocketMessage = JSON.parse(event.data);

                if (data.type === 'log') {
                    setLogs((prev) => [...prev, `[Agent] ${data.content}`]);
                } else if (data.type === 'slide_update') {
                    setLogs((prev) => [...prev, '[System] Hot-Reloading Slide...']);
                    setCurrentSlideCode(data.code);
                } else if (data.type === 'agent_message') {
                    // Append to dialogue (deduplicate if same content just loaded from history)
                    setDialogue((prev) => [...prev, data]);
                    // Also log it for transparency
                    setLogs((prev) => [...prev, `[${data.sender}] ${data.content.substring(0, 50)}...`]);
                } else if (data.type === 'progress') {
                    setProgress(data as ProgressData);
                }
            } catch (err) {
                console.error('Failed to parse WS message', err);
            }
        };

        ws.current.onclose = () => {
            setIsConnected(false);
            setLogs((prev) => [...prev, '[System] Disconnected. Reconnecting in 3s...']);

            // Auto-reconnect after 3 seconds
            if (!reconnectTimerRef.current) {
                reconnectTimerRef.current = setTimeout(() => {
                    reconnectTimerRef.current = null;
                    setReconnectCount(prev => prev + 1);
                }, 3000);
            }
        };
    };

    useEffect(() => {
        connect();

        // --- Keep-Alive Ping Interval (20s) ---
        const pingInterval = setInterval(() => {
            if (ws.current && ws.current.readyState === WebSocket.OPEN) {
                // Send silent ping
                ws.current.send(JSON.stringify({ type: 'ping', content: 'keep-alive' }));
            }
        }, 20000);

        return () => {
            clearInterval(pingInterval);
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            ws.current?.close();
        };
    }, [url, threadId, reconnectCount]);

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
        if (ws.current && isConnected) {
            const payload = JSON.stringify({ type: 'command', content: command });
            ws.current.send(payload);
            setLogs((prev) => [...prev, `[Command] Executing: ${command.toUpperCase()}`]);
        }
    };

    return { logs, dialogue, currentSlideCode, progress, sendMessage, sendCommand, isConnected };
}
