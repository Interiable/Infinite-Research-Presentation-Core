import React, { useState } from 'react';
import { Send, MessageSquare, Power } from 'lucide-react';

interface ChatProps {
    onSendMessage: (msg: string) => void;
    isConnected: boolean;
}

export const ChatPanel: React.FC<ChatProps> = ({ onSendMessage, isConnected }) => {
    const [input, setInput] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim()) {
            onSendMessage(input);
            setInput('');
        }
    };

    const handleShutdown = async () => {
        if (confirm("System Shutdown: Are you sure you want to stop all AI Agents and close the Mission Control?")) {
            try {
                await fetch('http://localhost:8000/api/stop', { method: 'POST' });
                alert("System Shutting Down...");
                window.close();
            } catch (err) {
                console.error("Shutdown failed", err);
            }
        }
    };

    return (
        <div className="flex flex-col h-2/3 bg-cyber-panel border-b border-cyber-border">
            <div className="flex items-center px-4 py-3 bg-cyber-dark border-b border-cyber-border justify-between">
                <div className="flex items-center">
                    <MessageSquare className="w-4 h-4 text-neon-blue mr-2" />
                    <span className="text-sm font-bold tracking-wider text-neon-blue">MISSION CONTROL</span>
                </div>
                <div className="flex items-center space-x-3">
                    <button
                        onClick={handleShutdown}
                        className="p-1 text-red-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                        title="Shutdown System"
                    >
                        <Power className="w-4 h-4" />
                    </button>
                    <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-neon-green animate-pulse' : 'bg-red-500'}`} />
                </div>
            </div>

            <div className="flex-1 p-4 overflow-y-auto">
                <div className="bg-cyber-dark/50 p-4 rounded-lg border border-cyber-border mb-4">
                    <p className="text-cyber-text text-sm">
                        박사님, 환영합니다. 연구 지시를 기다리고 있습니다.
                        <br />
                        현재 상태: <span className="text-neon-pink">대기 중 (Idle)</span>
                    </p>
                </div>
            </div>

            <form onSubmit={handleSubmit} className="p-4 bg-cyber-dark border-t border-cyber-border">
                <div className="relative">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Type directive..."
                        className="w-full bg-cyber-panel border border-cyber-border rounded-md py-3 pl-4 pr-12 text-sm text-white focus:outline-none focus:border-neon-blue transition-colors"
                    />
                    <button
                        type="submit"
                        className="absolute right-2 top-2 p-1 text-cyber-muted hover:text-neon-blue transition-colors"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </form>
        </div>
    );
};
