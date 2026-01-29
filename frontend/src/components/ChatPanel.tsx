import React, { useState, useEffect } from 'react';
import { Send, MessageSquare, Power, FolderOpen, Database } from 'lucide-react';

interface ChatProps {
    onSendMessage: (msg: string) => void;
    isConnected: boolean;
}

export const ChatPanel: React.FC<ChatProps> = ({ onSendMessage, isConnected }) => {
    const [input, setInput] = useState('');
    const [folders, setFolders] = useState<string[]>([]);
    const [showFolders, setShowFolders] = useState(false);

    useEffect(() => {
        fetchFolders();
    }, []);

    const fetchFolders = async () => {
        try {
            const res = await fetch('/api/config/folders');
            const data = await res.json();
            if (data.folders) setFolders(data.folders);
        } catch (err) {
            console.error("Failed to fetch folders", err);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim()) {
            onSendMessage(input);
            setInput('');
        }
    };

    const handlePickFolder = async () => {
        try {
            const res = await fetch('/api/config/pick-folder', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                // Refresh list
                await fetchFolders();
                alert(`폴더가 추가되었습니다.\n현재 연결된 폴더 수: ${data.path.split(',').length}개`);
            }
        } catch (err) {
            console.error("Folder pick failed", err);
        }
    };

    const handleShutdown = async () => {
        if (confirm("System Shutdown: Are you sure you want to stop all AI Agents and close the Mission Control?")) {
            try {
                await fetch('/api/stop', { method: 'POST' });
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
                        onClick={() => setShowFolders(!showFolders)}
                        className={`p-1 rounded transition-colors ${showFolders ? 'bg-neon-blue/20 text-neon-blue' : 'text-cyber-muted hover:text-neon-blue'}`}
                        title="View Data Sources"
                    >
                        <Database className="w-4 h-4" />
                    </button>
                    <button
                        onClick={handlePickFolder}
                        className="p-1 text-neon-blue hover:bg-neon-blue/10 rounded transition-colors"
                        title="Add Research Folder"
                    >
                        <FolderOpen className="w-4 h-4" />
                    </button>
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
                    <p className="text-cyber-text text-sm mb-2">
                        박사님, 환영합니다. 연구 지시를 기다리고 있습니다.
                        <br />
                        현재 상태: <span className="text-neon-pink">대기 중 (Idle)</span>
                    </p>

                    {/* Folder List UI */}
                    {showFolders && (
                        <div className="mt-3 p-3 bg-black/40 rounded border border-cyber-border">
                            <h4 className="text-xs font-bold text-neon-green mb-2 flex items-center">
                                <Database className="w-3 h-3 mr-1" /> LINKED KNOWLEDGE BASES ({folders.length})
                            </h4>
                            {folders.length > 0 ? (
                                <ul className="space-y-1">
                                    {folders.map((path, idx) => (
                                        <li key={idx} className="text-xs text-cyber-muted break-all flex items-start">
                                            <span className="mr-2 text-cyber-border">•</span>
                                            {path}
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-xs text-cyber-muted italic">No local folders linked yet.</p>
                            )}
                        </div>
                    )}
                </div>
            </div>

            <form onSubmit={handleSubmit} className="p-4 bg-cyber-dark border-t border-cyber-border">
                <div className="relative">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSubmit(e);
                            }
                        }}
                        placeholder="Type directive... (Shift+Enter for new line)"
                        className="w-full h-24 bg-cyber-panel border border-cyber-border rounded-md py-3 pl-4 pr-12 text-sm text-white focus:outline-none focus:border-neon-blue transition-colors resize-none"
                    />
                    <button
                        type="submit"
                        className="absolute right-2 bottom-2 p-1 text-cyber-muted hover:text-neon-blue transition-colors"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </form>
        </div>
    );
};
