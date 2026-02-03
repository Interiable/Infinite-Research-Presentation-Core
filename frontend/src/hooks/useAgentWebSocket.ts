import { useEffect, useRef, useState } from 'react';

type LogMessage = {
    type: 'log';
    content: string;
};

type SlideUpdate = {
    type: 'slide_update';
    code: string;
    version?: number;
};

type WebSocketMessage = LogMessage | SlideUpdate;

export function useAgentWebSocket(url: string, threadId: string) {
    const ws = useRef<WebSocket | null>(null);
    const [logs, setLogs] = useState<string[]>([]);
    const [currentSlideCode, setCurrentSlideCode] = useState<string | null>(null);
    const [isConnected, setIsConnected] = useState(false);

    useEffect(() => {
        if (!threadId) return;

        const wsUrl = `${url}/${threadId}`;
        console.log(`Connecting to session: ${threadId}`);

        ws.current = new WebSocket(wsUrl);

        ws.current.onopen = () => {
            console.log('Connected to Agent Stream');
            setIsConnected(true);
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
                }
            } catch (err) {
                console.error('Failed to parse WS message', err);
            }
        };

        ws.current.onclose = () => {
            setIsConnected(false);
            setLogs((prev) => [...prev, '[System] Disconnected']);
        };

        return () => {
            ws.current?.close();
        };
    }, [url, threadId]);

    const sendMessage = (text: string) => {
        if (ws.current && isConnected) {
            // Send as JSON structure for better backend parsing
            const payload = JSON.stringify({ type: 'message', content: text });
            ws.current.send(payload);
            setLogs((prev) => [...prev, `[User] ${text}`]);
        }
    };

    const sendCommand = (command: string) => {
        if (ws.current && isConnected) {
            const payload = JSON.stringify({ type: 'command', content: command });
            ws.current.send(payload);
            setLogs((prev) => [...prev, `[Command] Executing: ${command.toUpperCase()}`]);
        }
    };

    return { logs, currentSlideCode, sendMessage, sendCommand, isConnected };
}
