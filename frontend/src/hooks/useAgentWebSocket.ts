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

export function useAgentWebSocket(url: string) {
    const ws = useRef<WebSocket | null>(null);
    const [logs, setLogs] = useState<string[]>([]);
    const [currentSlideCode, setCurrentSlideCode] = useState<string | null>(null);
    const [isConnected, setIsConnected] = useState(false);

    useEffect(() => {
        // Generate a random client ID
        const clientId = Math.random().toString(36).substring(7);
        const wsUrl = `${url}/${clientId}`;

        ws.current = new WebSocket(wsUrl);

        ws.current.onopen = () => {
            console.log('Connected to Agent Stream');
            setIsConnected(true);
            setLogs((prev) => [...prev, '[System] Connected to Mission Control']);
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
    }, [url]);

    const sendMessage = (text: string) => {
        if (ws.current && isConnected) {
            ws.current.send(text);
            setLogs((prev) => [...prev, `[User] ${text}`]);
        }
    };

    return { logs, currentSlideCode, sendMessage, isConnected };
}
