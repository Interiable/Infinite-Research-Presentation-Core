import React, { useEffect, useRef } from 'react';
import { Bot, User, BrainCircuit, Search, Edit3, Shield, BookOpen, Wand2, RefreshCcw } from 'lucide-react';

interface AgentMessage {
    type: 'agent_message';
    sender: string;
    content: string;
    timestamp?: string;
}

interface AgentDialogueProps {
    messages: AgentMessage[];
}

const getAgentIcon = (sender: string) => {
    const s = sender.toLowerCase();
    if (s === 'user') return <User className="w-4 h-4" />;
    if (s.includes('planner')) return <BrainCircuit className="w-4 h-4" />;
    if (s.includes('supervisor')) return <Shield className="w-4 h-4" />;
    if (s.includes('deep')) return <Search className="w-4 h-4" />;
    if (s.includes('researcher')) return <Edit3 className="w-4 h-4" />;
    if (s.includes('archivist')) return <BookOpen className="w-4 h-4" />;
    if (s.includes('architect')) return <Wand2 className="w-4 h-4" />;
    if (s.includes('refiner')) return <RefreshCcw className="w-4 h-4" />;
    return <Bot className="w-4 h-4" />;
};

const getAgentColor = (sender: string) => {
    const s = sender.toLowerCase();
    if (s === 'user') return 'text-cyan-300 border-cyan-400/40 bg-cyan-500/15';
    if (s.includes('planner')) return 'text-purple-400 border-purple-500/30 bg-purple-500/10';
    if (s.includes('supervisor')) return 'text-red-400 border-red-500/30 bg-red-500/10';
    if (s.includes('deep')) return 'text-blue-400 border-blue-500/30 bg-blue-500/10';
    if (s.includes('researcher')) return 'text-green-400 border-green-500/30 bg-green-500/10';
    if (s.includes('archivist')) return 'text-amber-400 border-amber-500/30 bg-amber-500/10';
    if (s.includes('architect')) return 'text-pink-400 border-pink-500/30 bg-pink-500/10';
    if (s.includes('refiner')) return 'text-teal-400 border-teal-500/30 bg-teal-500/10';
    return 'text-cyber-text border-cyber-border bg-black/20';
};

const isUserMessage = (sender: string) => sender.toLowerCase() === 'user';

export const AgentDialogue: React.FC<AgentDialogueProps> = ({ messages }) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    return (
        <div className="flex flex-col h-full overflow-hidden bg-black/40 rounded border border-cyber-border">
            <div className="flex items-center px-3 py-2 bg-black/60 border-b border-cyber-border">
                <span className="flex w-2 h-2 rounded-full bg-neon-green animate-pulse mr-2"></span>
                <span className="text-xs font-bold text-cyber-text tracking-wider">AGENT NEURAL LINK (LIVE)</span>
                {messages.length > 0 && (
                    <span className="ml-auto text-[10px] text-cyber-muted font-mono">{messages.length} messages</span>
                )}
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {messages.length === 0 ? (
                    <div className="text-center text-cyber-muted text-xs italic mt-10">
                        Waiting for agent transmission...
                    </div>
                ) : (
                    messages.map((msg, idx) => {
                        const isUser = isUserMessage(msg.sender);

                        return (
                            <div
                                key={idx}
                                className={`group flex flex-col animate-in fade-in slide-in-from-bottom-2 duration-300 ${isUser ? 'items-end' : 'items-start'
                                    }`}
                            >
                                <div className={`flex items-center mb-1 ${isUser ? 'mr-1' : 'ml-1'} opacity-70 group-hover:opacity-100 transition-opacity`}>
                                    <span className={`mr-1 ${getAgentColor(msg.sender).split(' ')[0]}`}>
                                        {getAgentIcon(msg.sender)}
                                    </span>
                                    <span className="text-[10px] font-mono uppercase text-cyber-muted">{msg.sender}</span>
                                    {msg.timestamp && (
                                        <span className="text-[9px] font-mono text-cyber-muted/50 ml-2">
                                            {new Date(msg.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
                                        </span>
                                    )}
                                </div>

                                <div className={`
                                    relative px-3 py-2 text-xs leading-relaxed max-w-[90%] border backdrop-blur-sm whitespace-pre-wrap break-words
                                    ${isUser
                                        ? 'rounded-l-lg rounded-br-lg bg-cyan-500/15 border-cyan-400/30 text-cyan-100'
                                        : 'rounded-r-lg rounded-bl-lg ' + getAgentColor(msg.sender)
                                    }
                                `}>
                                    {/* Triangle for bubble */}
                                    {isUser ? (
                                        <div className="absolute top-0 right-[-4px] w-0 h-0 border-t-[6px] border-t-transparent border-l-[6px] border-l-cyan-400/20"></div>
                                    ) : (
                                        <div className="absolute top-0 left-[-4px] w-0 h-0 border-t-[6px] border-t-transparent border-r-[6px] border-r-current opacity-20 transform rotate-180"></div>
                                    )}
                                    {msg.content}
                                </div>
                            </div>
                        );
                    })
                )}
                <div ref={scrollRef} />
            </div>
        </div>
    );
};
