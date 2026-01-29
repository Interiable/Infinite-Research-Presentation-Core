import React, { useEffect, useRef } from 'react';
import { Terminal as TerminalIcon } from 'lucide-react';

interface TerminalProps {
    logs: string[];
}

export const Terminal: React.FC<TerminalProps> = ({ logs }) => {
    const endRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    return (
        <div className="flex flex-col h-1/3 bg-cyber-panel border-t border-cyber-border">
            <div className="flex items-center px-4 py-2 bg-cyber-dark border-b border-cyber-border">
                <TerminalIcon className="w-4 h-4 text-neon-green mr-2" />
                <span className="text-xs font-mono text-neon-green">SYSTEM LOGS</span>
            </div>
            <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-1 text-cyber-muted">
                {logs.map((log, i) => (
                    <div key={i} className="break-words">
                        <span className="text-cyber-border mr-2">
                            {new Date().toLocaleTimeString()}
                        </span>
                        <span className={log.startsWith('[User]') ? 'text-neon-pink' : 'text-cyber-text'}>
                            {log}
                        </span>
                    </div>
                ))}
                <div ref={endRef} />
            </div>
        </div>
    );
};
