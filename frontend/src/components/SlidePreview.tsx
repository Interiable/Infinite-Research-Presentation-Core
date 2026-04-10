import React, { useState, useEffect } from 'react';
import { Play, SkipForward, Grid } from 'lucide-react';
import * as LucideIcons from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { LiveProvider, LiveError, LivePreview } from 'react-live';
import * as Recharts from 'recharts';

interface SlidePreviewProps {
    code: string | null;
    progress?: any;
}

// Helper to filter valid identifiers
const isValidIdentifier = (key: string) => /^[a-zA-Z_$][a-zA-Z0-9_$]*$/.test(key);

// Scope for the Live Preview (Exposure of libraries)
const { Presentation: _IconPresentation, ...AllLucideIcons } = LucideIcons as any;

// Sanitize Lucide Icons
const SafeLucideIcons = Object.keys(AllLucideIcons).reduce((acc, key) => {
    if (isValidIdentifier(key)) {
        acc[key] = AllLucideIcons[key];
    }
    return acc;
}, {} as any);

// Handle Recharts ESM/CJS interop & Sanitize
const RechartsModule = Recharts as any;
const MergedRecharts = { ...RechartsModule, ...(RechartsModule.default || {}) };
const SafeRecharts = Object.keys(MergedRecharts).reduce((acc, key) => {
    if (isValidIdentifier(key)) {
        acc[key] = MergedRecharts[key];
    }
    return acc;
}, {} as any);

// Initial static scope (React core)
const BaseScope = {
    React,
    useState,
    useEffect,
    motion,
    AnimatePresence,
};

// ... existing code ...

export const SlidePreview: React.FC<SlidePreviewProps> = ({ code, progress }) => {

    // Dynamically build scope to avoid collisions
    const scope = React.useMemo(() => {
        if (!code) return { ...BaseScope };

        // 1. Gather all declarations in user code to avoid collision
        // Regex to find: const X, let X, var X, function X, class X
        const declaredVars = new Set();
        const declRegex = /(?:const|let|var|function|class)\s+(\w+)/g;
        let match;
        while ((match = declRegex.exec(code)) !== null) {
            declaredVars.add(match[1]);
        }

        // 2. Filter Lucide Icons
        const SafeLucide = Object.keys(AllLucideIcons).reduce((acc, key) => {
            if (isValidIdentifier(key) && !declaredVars.has(key)) {
                acc[key] = AllLucideIcons[key];
            }
            return acc;
        }, {} as any);

        // 3. Filter Recharts
        const SafeRechartsFiltered = Object.keys(MergedRecharts).reduce((acc, key) => {
            if (isValidIdentifier(key) && !declaredVars.has(key)) {
                acc[key] = MergedRecharts[key];
            }
            return acc;
        }, {} as any);

        return {
            ...BaseScope,
            ...SafeLucide,
            ...SafeRechartsFiltered,
        };
    }, [code]);

    // ... existing transformCode ...

    const transformCode = (rawCode: string) => {
        if (!rawCode) return "";

        // 1. Line-based Import Stripping (Robust state machine)
        const lines = rawCode.split('\n');
        let insideImport = false;

        const cleanLines = lines.filter(line => {
            const trimmed = line.trim();
            if (trimmed.startsWith('import ') || trimmed.startsWith('import{')) {
                if (trimmed.includes('from') && trimmed.includes(';')) return false;
                insideImport = true;
                return false;
            }
            if (insideImport) {
                if (trimmed.includes('from') && trimmed.includes(';')) insideImport = false;
                return false;
            }
            return true;
        });

        let cleanCode = cleanLines.join('\n');

        // 2. Detect the exported component name (Greedy check for the first one)
        let componentName = "Presentation"; // Default fallback

        // Regex to match "export default function Name" or "export default Name"
        const defaultFuncMatch = cleanCode.match(/export\s+default\s+function\s+(\w+)/);
        const defaultVarMatch = cleanCode.match(/export\s+default\s+(\w+)/);

        if (defaultFuncMatch) {
            componentName = defaultFuncMatch[1];
        } else if (defaultVarMatch) {
            componentName = defaultVarMatch[1];
        }

        // 3. Global Cleanup of Export Keywords to prevent "exports is not defined"
        // Replace "export default" with nothing (turning "export default Slide1;" into "Slide1;")
        cleanCode = cleanCode.replace(/export\s+default\s+/g, '');

        // Replace named exports "export const" -> "const"
        cleanCode = cleanCode.replace(/^\s*export\s+/gm, '');

        // 4. Append render
        cleanCode += `\nrender(<${componentName} />);`;

        return cleanCode;
    };

    const finalCode = transformCode(code || "");

    return (
        <div className="flex flex-col h-full bg-black relative overflow-hidden">
            <div className="flex-1 flex items-center justify-center p-8 bg-neutral-900/50">
                <div className="aspect-video w-full max-w-7xl h-full bg-cyber-panel border border-cyber-border rounded-xl shadow-2xl overflow-hidden relative group">
                    {code ? (
                        <LiveProvider
                            code={finalCode}
                            scope={scope}
                            noInline={true}
                            theme={{
                                plain: { color: "#e2e8f0", backgroundColor: "#0f172a" },
                                styles: []
                            }}
                        >
                            <LivePreview className="w-full h-full" />

                            {/* Error Overlay */}
                            <div className="absolute bottom-0 left-0 w-full z-50 pointer-events-none">
                                <LiveError className="bg-red-500/90 text-white p-4 text-xs font-mono backdrop-blur-sm" />
                            </div>
                        </LiveProvider>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-full text-cyber-muted">
                            <div className="w-16 h-16 border-2 border-cyber-border border-dashed rounded-full animate-spin-slow mb-4" />
                            <p>Waiting for slide data...</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Control Bar */}
            <div className="h-16 bg-cyber-panel border-t border-cyber-border flex items-center justify-between px-8 z-50 relative">
                <div className="flex items-center space-x-4">
                    <button className="p-2 hover:bg-cyber-dark rounded-md text-cyber-text transition-colors">
                        <span className="font-mono text-neon-pink text-sm">v1.2</span>
                    </button>
                </div>
                
                {/* Progress Bar (Centered in footer) */}
                {progress && progress.total_steps > 0 && (
                    <div className="flex-1 flex flex-col items-center justify-center px-8 max-w-2xl">
                        <div className="flex w-full items-center justify-between text-[10px] md:text-xs text-slate-400 mb-1">
                            <span>📊 Step {progress.current_step}/{progress.total_steps}{progress.total_subs > 0 ? ` · Sub ${progress.current_sub}/${progress.total_subs}` : ''}</span>
                            <span className="text-cyan-400 font-mono font-bold ml-4">{progress.percent}%</span>
                        </div>
                        <div className="w-full bg-slate-800/80 border border-slate-700 rounded-full h-1.5 overflow-hidden">
                            <div
                                className="h-full rounded-full bg-gradient-to-r from-neon-pink to-neon-purple transition-all duration-700 ease-out"
                                style={{ width: `${progress.percent}%` }}
                            />
                        </div>
                        <div className="text-[9px] text-slate-500 mt-1 max-w-full truncate text-center flex gap-2">
                           <span className="text-neon-green">▸ {progress.next_agent}</span>
                           <span>{progress.task_name && `- ${progress.task_name}`}</span>
                        </div>
                    </div>
                )}

                <div className="text-xs font-mono text-slate-500">
                    LIVE RENDERER ACTIVE
                </div>
            </div>
        </div>
    );
};
