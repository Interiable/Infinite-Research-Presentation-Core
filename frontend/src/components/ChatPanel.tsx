import React, { useState } from 'react';
import { Send, MessageSquare } from 'lucide-react';

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

    return (
        <div className="flex flex-col h-2/3 bg-cyber-panel border-b border-cyber-border">
            <div className="flex items-center px-4 py-3 bg-cyber-dark border-b border-cyber-border">
                <MessageSquare className="w-4 h-4 text-neon-blue mr-2" />
                <span className="text-sm font-bold tracking-wider text-neon-blue">MISSION CONTROL</span>
                <div className={`ml-auto w-2 h-2 rounded-full ${isConnected ? 'bg-neon-green animate-pulse' : 'bg-red-500'}`} />
            </div>

            <div className="flex-1 p-4 overflow-y-auto">
                <div className="bg-cyber-dark/50 p-4 rounded-lg border border-cyber-border mb-4">
                    <p className="text-cyber-text text-sm">
                        Hello Director. I am ready for your instructions.
                        <br />
                        Current Target: <span className="text-neon-pink">Idle</span>
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
