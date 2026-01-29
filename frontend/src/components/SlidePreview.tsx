import React from 'react';
import { Play, SkipForward, Grid } from 'lucide-react';
import { motion } from 'framer-motion';

interface SlidePreviewProps {
    code: string | null;
}

export const SlidePreview: React.FC<SlidePreviewProps> = ({ code }) => {
    return (
        <div className="flex flex-col h-full bg-black relative overflow-hidden">
            {/* Simulation of the Slide Stage (16:9) */}
            <div className="flex-1 flex items-center justify-center p-8">
                <div className="aspect-video w-full max-w-5xl bg-cyber-panel border border-cyber-border rounded-xl shadow-2xl overflow-hidden relative group">

                    {code ? (
                        <div className="w-full h-full flex flex-col items-center justify-center text-cyber-muted">
                            {/* 
                  TODO: Integrate @monaco-editor/react or react-live for real rendering.
                  For now, we display the raw code as a proof of hot-swap.
               */}
                            <pre className="text-xs text-left p-4 overflow-auto max-h-full w-full bg-cyber-dark/90 text-neon-green font-mono">
                                {code}
                            </pre>
                            <div className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                                <span className="text-white font-bold">Rendering Engine v2026 Active</span>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-full text-cyber-muted">
                            <div className="w-16 h-16 border-2 border-cyber-border border-dashed rounded-full animate-spin-slow mb-4" />
                            <p>Waiting for slide data...</p>
                        </div>
                    )}

                </div>
            </div>

            {/* Control Bar */}
            <div className="h-16 bg-cyber-panel border-t border-cyber-border flex items-center justify-between px-8">
                <div className="flex items-center space-x-4">
                    <button className="p-2 hover:bg-cyber-dark rounded-md text-cyber-text transition-colors">
                        <span className="font-mono text-neon-pink text-sm">v1.0</span>
                    </button>
                    <div className="h-4 w-px bg-cyber-border" />
                    <button className="p-2 hover:bg-cyber-dark rounded-md text-cyber-text transition-colors">
                        <Grid className="w-5 h-5" />
                    </button>
                </div>

                <div className="flex items-center space-x-6">
                    <button className="p-3 bg-neon-green/10 text-neon-green rounded-full hover:bg-neon-green/20 transition-colors">
                        <Play className="w-6 h-6 fill-current" />
                    </button>
                </div>

                <div className="flex items-center space-x-4">
                    <button className="p-2 hover:bg-cyber-dark rounded-md text-cyber-text transition-colors">
                        <SkipForward className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
};
