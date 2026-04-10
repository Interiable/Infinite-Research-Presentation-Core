import React, { useState, useEffect, useRef } from 'react';
import { Send, MessageSquare, Power, FolderOpen, Database, PauseCircle, PlayCircle, PlusCircle, Hash, History } from 'lucide-react';
import { AgentDialogue } from './AgentDialogue';

interface ChatProps {
    onSendMessage: (msg: string, config?: any, projectId?: string) => void;
    onSendCommand: (cmd: string) => void;
    isConnected: boolean;
    logs: string[];
    dialogue: any[]; // Using any to avoid strict type duplication here, or export AgentMessage
    threadId: string;
    onNewSession: () => void;
}

export const ChatPanel: React.FC<ChatProps> = ({
    onSendMessage,
    onSendCommand,
    isConnected,
    logs,
    dialogue,
    threadId,
    onNewSession
}) => {
    const [input, setInput] = useState('');
    const [currentProject, setCurrentProject] = useState(() => localStorage.getItem('agent_project_id') || 'default');
    const [isCustomWorkspace, setIsCustomWorkspace] = useState(false);
    const [useWebSearch, setUseWebSearch] = useState(true);
    const [usePaperSearch, setUsePaperSearch] = useState(true);
    const [usePatentSearch, setUsePatentSearch] = useState(true);
    const [useMediaSearch, setUseMediaSearch] = useState(true);
    const [projects, setProjects] = useState<string[]>([]);
    const [folders, setFolders] = useState<string[]>([]);
    const [historyThreads, setHistoryThreads] = useState<any[]>([]);
    const [commandHistory, setCommandHistory] = useState<any[]>([]);
    const [showFolders, setShowFolders] = useState(false);
    const [showHistory, setShowHistory] = useState(false);
    const logsEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        fetchProjects();
        fetchHistory();
    }, []);

    useEffect(() => {
        localStorage.setItem('agent_project_id', currentProject);
        fetchFolders();
    }, [currentProject]);

    // Auto-scroll logs
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    const fetchHistory = async () => {
        try {
            const res = await fetch('/api/threads');
            const data = await res.json();
            if (data.threads) setHistoryThreads(data.threads);
        } catch (err) {
            console.error("Failed to fetch history", err);
        }
    };

    const fetchProjects = async () => {
        try {
            const res = await fetch('/api/config/projects');
            const data = await res.json();
            if (data.projects) setProjects(data.projects);
        } catch (err) {
            console.error("Failed to fetch projects", err);
        }
    };

    const fetchFolders = async () => {
        try {
            const res = await fetch(`/api/config/folders?project_id=${currentProject}`);
            const data = await res.json();
            if (data.folders) setFolders(data.folders);
        } catch (err) {
            console.error("Failed to fetch folders", err);
        }
    };

    const fetchCommandHistory = async () => {
        if (!threadId) return;
        try {
            const res = await fetch(`/api/chat/history/${threadId}`);
            const data = await res.json();
            if (data.history) setCommandHistory(data.history);
        } catch (err) {
            console.error("Failed to fetch command history", err);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim()) {
            onSendMessage(input, { web: useWebSearch, academic: usePaperSearch, patent: usePatentSearch, media: useMediaSearch }, currentProject);
            setInput('');
        }
    };

    const handlePickFolder = async () => {
        try {
            const res = await fetch(`/api/config/pick-folder?project_id=${currentProject}`, { method: 'POST' });
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

    const handleDeleteThread = async (id: string) => {
        if (confirm(`정말로 이 토픽(${id})과 관련된 모든 데이터(체크포인트, 결과 보고서)를 삭제하시겠습니까?`)) {
            try {
                const res = await fetch(`/api/threads/${id}`, { method: 'DELETE' });
                const data = await res.json();
                if (data.status === 'success') {
                    if (id === threadId) {
                        onNewSession();
                    } else {
                        await fetchHistory();
                    }
                }
            } catch (err) {
                console.error("Delete failed", err);
            }
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

    // --- TAB STATE ---
    const [activeTab, setActiveTab] = useState<'log' | 'dialogue'>('dialogue'); // Default to dialogue as user requested

    return (
        <div className="flex flex-col h-full bg-cyber-panel border-b border-cyber-border">
            {/* Header */}
            <div className="flex flex-col bg-cyber-dark border-b border-cyber-border">
                {/* Top Row: System Status & Global Controls */}
                <div className="flex items-center px-4 py-2 border-b border-cyber-border justify-between">
                    <div className="flex items-center">
                        <MessageSquare className="w-4 h-4 text-neon-blue mr-2" />
                        <span className="text-sm font-bold tracking-wider text-neon-blue">MISSION CONTROL</span>
                    </div>
                    {/* ... (omitted buttons) ... */}
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
                            onClick={() => {
                                setShowHistory(!showHistory);
                                if (!showHistory) fetchCommandHistory();
                            }}
                            className={`p-1 rounded transition-colors ${showHistory ? 'bg-neon-pink/20 text-neon-pink' : 'text-cyber-muted hover:text-neon-pink'}`}
                            title="View Command History"
                        >
                            <History className="w-4 h-4" />
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

                {/* Second Row: Session Management */}
                <div className="flex items-center px-4 py-2 bg-black/20 justify-between">
                    <div className="flex items-center gap-2">
                        <div className="flex items-center bg-black/40 border border-cyber-border rounded px-2 py-0.5">
                            <span className="text-[10px] text-cyber-muted mr-1">WORKSPACE:</span>
                            {isCustomWorkspace ? (
                                <div className="flex items-center">
                                    <input
                                        autoFocus
                                        type="text"
                                        value={currentProject}
                                        onChange={(e) => setCurrentProject(e.target.value)}
                                        onKeyDown={(e) => { if (e.key === 'Enter') setIsCustomWorkspace(false); }}
                                        className="bg-transparent text-[10px] font-mono text-neon-blue focus:outline-none w-20"
                                        placeholder="Type & Enter"
                                    />
                                    <button onClick={() => { setIsCustomWorkspace(false); if(!currentProject) setCurrentProject('default'); }} className="text-red-500 hover:text-red-400 ml-1 text-xs">×</button>
                                </div>
                            ) : (
                                <select
                                    value={projects.includes(currentProject) ? currentProject : (currentProject ? currentProject : '__NEW__')}
                                    onChange={(e) => {
                                        if (e.target.value === '__NEW__') {
                                            setIsCustomWorkspace(true);
                                            setCurrentProject('');
                                        } else {
                                            setCurrentProject(e.target.value);
                                        }
                                    }}
                                    className="bg-transparent text-[10px] font-mono text-neon-blue focus:outline-none cursor-pointer w-24 appearance-none"
                                >
                                    {projects.map(p => (
                                        <option key={p} value={p} className="bg-cyber-dark text-neon-blue">{p}</option>
                                    ))}
                                    {!projects.includes(currentProject) && currentProject && (
                                        <option key={currentProject} value={currentProject} className="bg-cyber-dark text-neon-blue">{currentProject}</option>
                                    )}
                                    <option value="__NEW__" className="bg-cyber-dark text-neon-pink">➕ Create New...</option>
                                </select>
                            )}
                        </div>
                        <div className="flex items-center gap-1 hidden md:flex">
                            <Hash size={12} />
                            <span className="font-mono text-xs">ID: {threadId}</span>
                        </div>
                    </div>

                    {/* Session Manager Trigger */}
                    <div className="relative group ml-2">
                        <button
                            onClick={() => setShowHistory(!showHistory)}
                            className={`flex items-center gap-1 px-2 py-0.5 rounded border transition-all text-[10px] font-mono ${showHistory ? 'bg-neon-pink/20 border-neon-pink text-neon-pink' : 'bg-black/40 border-cyber-border text-cyber-muted hover:border-neon-pink hover:text-neon-pink'}`}
                        >
                            <History size={10} />
                            TOPIC MANAGER
                        </button>

                        {/* Floating Dropdown for Thread Management */}
                        {showHistory && (
                            <div className="absolute top-full right-0 mt-1 w-64 bg-cyber-dark border border-cyber-border shadow-2xl rounded-md z-50 p-2 overflow-hidden animate-in fade-in slide-in-from-top-1">
                                <div className="text-[10px] font-bold text-cyber-muted mb-2 border-b border-cyber-border pb-1 flex justify-between items-center px-1">
                                    <span>LOAD PREVIOUS TOPIC</span>
                                    <button onClick={() => setShowHistory(false)} className="hover:text-neon-pink p-1">×</button>
                                </div>
                                <div className="max-h-48 overflow-y-auto space-y-1 custom-scrollbar pr-1">
                                    {historyThreads.filter(t => t.project_id === currentProject).map(t => (
                                        <div key={t.id} className={`flex items-center justify-between p-1.5 rounded text-[10px] font-mono group/item ${t.id === threadId ? 'bg-neon-blue/20 border border-neon-blue/30' : 'hover:bg-white/5 border border-transparent'}`}>
                                            <button
                                                onClick={() => {
                                                    if (t.id !== threadId) {
                                                        localStorage.setItem('agent_thread_id', t.id);
                                                        window.location.reload();
                                                    }
                                                }}
                                                className={`flex-1 text-left truncate px-1 ${t.id === threadId ? 'text-neon-blue' : 'text-cyber-text'}`}
                                                title={t.id}
                                            >
                                                {t.id === threadId ? "▶ " : ""}{t.id}
                                            </button>
                                            <button
                                                onClick={() => handleDeleteThread(t.id)}
                                                className="p-1 text-red-500/50 hover:text-red-500 transition-all flex-shrink-0"
                                                title="Delete Topic & Data"
                                            >
                                                <PlusCircle size={10} className="rotate-45" />
                                            </button>
                                        </div>
                                    ))}
                                    {historyThreads.filter(t => t.project_id === currentProject).length === 0 && (
                                        <div className="text-[10px] text-cyber-muted italic p-2">No history found for [{currentProject}].</div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <button
                    onClick={onNewSession}
                    className="flex items-center gap-1 text-xs text-neon-pink hover:text-white transition-colors"
                >
                    <PlusCircle size={12} />
                    New Topic
                </button>
            </div>

            <div className="flex-1 p-4 overflow-hidden flex flex-col min-h-0">
                <div className="bg-cyber-dark/50 p-2 rounded-lg border border-cyber-border mb-4 flex-1 flex flex-col min-h-0">

                    {/* TAB SWITCHER */}
                    <div className="flex border-b border-cyber-border/50 mb-2">
                        <button
                            className={`px-3 py-1 text-xs font-bold transition-all border-b-2 ${activeTab === 'dialogue' ? 'text-neon-green border-neon-green' : 'text-cyber-muted border-transparent hover:text-white'}`}
                            onClick={() => setActiveTab('dialogue')}
                        >
                            AGENT CHAT
                        </button>
                        <button
                            className={`px-3 py-1 text-xs font-bold transition-all border-b-2 ${activeTab === 'log' ? 'text-neon-blue border-neon-blue' : 'text-cyber-muted border-transparent hover:text-white'}`}
                            onClick={() => setActiveTab('log')}
                        >
                            SYSTEM LOGS
                        </button>
                    </div>

                    {/* CONTENT AREA */}
                    <div className="flex-1 min-h-0 overflow-hidden relative">
                        {activeTab === 'dialogue' ? (
                            <AgentDialogue messages={dialogue} />
                        ) : (
                            <div className="p-3 bg-black/60 rounded border border-cyber-border h-full overflow-y-auto font-mono text-xs">
                                <div className="space-y-1">
                                    {logs.map((log, i) => (
                                        <div key={i} className="text-cyber-text break-words">
                                            <span className="text-cyber-muted mr-2">[{i + 1}]</span>
                                            {log}
                                        </div>
                                    ))}
                                    <div ref={logsEndRef} />
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Folder List UI (Collapsible) */}
                    {showFolders && (
                        <div className="mt-3 p-3 bg-black/40 rounded border border-cyber-border flex-shrink-0">
                            <h4 className="text-xs font-bold text-neon-green mb-2 flex items-center">
                                <Database className="w-3 h-3 mr-1" /> LINKED KNOWLEDGE BASES ({folders.length})
                            </h4>
                            {folders.length > 0 ? (
                                <ul className="space-y-1 max-h-24 overflow-y-auto">
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

                    {/* Command History UI (Collapsible) */}
                    {showHistory && (
                        <div className="mt-3 p-3 bg-black/40 rounded border border-cyber-border h-32 overflow-y-auto flex-shrink-0">
                            <h4 className="text-xs font-bold text-neon-pink mb-2 flex items-center border-b border-cyber-border pb-1">
                                <History className="w-3 h-3 mr-1" /> USER COMMAND HISTORY
                            </h4>
                            <div className="space-y-2">
                                {commandHistory.length > 0 ? (
                                    commandHistory.map((cmd, idx) => (
                                        <div key={idx} className="text-xs border-l-2 border-neon-pink pl-2 py-1">
                                            <div className="text-cyber-muted text-[10px] mb-0.5">{cmd.timestamp || "Just now"}</div>
                                            <div className="text-cyber-text">{cmd.content}</div>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-xs text-cyber-muted italic">No commands recorded yet.</p>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <form onSubmit={handleSubmit} className="p-4 bg-cyber-dark border-t border-cyber-border flex-shrink-0 flex flex-col gap-2">
                {/* Pause/Resume Buttons */}
                <div className="flex justify-center gap-2 mb-1">
                    <button
                        type="button"
                        onClick={() => onSendCommand("pause")}
                        className="bg-slate-800 text-neon-pink hover:bg-slate-700 hover:text-white px-3 py-1.5 rounded-full text-[10px] md:text-sm flex items-center gap-1 border border-cyber-border shadow-lg transition-all"
                    >
                        <PauseCircle size={14} />
                        Pause / Interrupt
                    </button>
                    <button
                        type="button"
                        onClick={() => onSendMessage("RESUME", undefined, currentProject)}
                        className="bg-slate-800 text-neon-green hover:bg-slate-700 hover:text-white px-3 py-1.5 rounded-full text-[10px] md:text-sm flex items-center gap-1 border border-cyber-border shadow-lg transition-all"
                    >
                        <PlayCircle size={14} />
                        Resume Research
                    </button>
                </div>

                <div className="flex flex-wrap items-center gap-4 px-1 mb-1 text-[10px] md:text-sm text-cyber-muted">
                    <label className="flex items-center cursor-pointer hover:text-white transition-colors">
                        <input
                            type="checkbox"
                            checked={useWebSearch}
                            onChange={(e) => setUseWebSearch(e.target.checked)}
                            className="mr-1.5 accent-neon-blue rounded-sm cursor-pointer"
                        />
                        Web Search
                    </label>
                    <label className="flex items-center cursor-pointer hover:text-white transition-colors">
                        <input
                            type="checkbox"
                            checked={usePaperSearch}
                            onChange={(e) => setUsePaperSearch(e.target.checked)}
                            className="mr-1.5 accent-neon-pink rounded-sm cursor-pointer"
                        />
                        Paper Search
                    </label>
                    <label className="flex items-center cursor-pointer hover:text-white transition-colors">
                        <input
                            type="checkbox"
                            checked={usePatentSearch}
                            onChange={(e) => setUsePatentSearch(e.target.checked)}
                            className="mr-1.5 accent-neon-green rounded-sm cursor-pointer"
                        />
                        Patent Search
                    </label>
                    <label className="flex items-center cursor-pointer hover:text-white transition-colors">
                        <input
                            type="checkbox"
                            checked={useMediaSearch}
                            onChange={(e) => setUseMediaSearch(e.target.checked)}
                            className="mr-1.5 accent-neon-yellow rounded-sm cursor-pointer"
                        />
                        Media Search
                    </label>
                </div>

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

