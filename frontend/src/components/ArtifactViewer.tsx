import React, { useState, useEffect } from 'react';
import { SlidePreview } from './SlidePreview';
import { MarkdownPreview } from './MarkdownPreview';
import { FileText, RefreshCw, LayoutTemplate, Download } from 'lucide-react';

interface ArtifactViewerProps {
    onClose: () => void;
    threadId: string;
}

export const ArtifactViewer: React.FC<ArtifactViewerProps> = ({ onClose, threadId }) => {
    const [files, setFiles] = useState<string[]>([]);
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [fileContent, setFileContent] = useState<string>("");
    const [loading, setLoading] = useState(false);

    const fetchFiles = async () => {
        try {
            const res = await fetch(`http://localhost:8000/api/artifacts?thread_id=${threadId}`);
            const data = await res.json();
            if (data.files) {
                setFiles(data.files);
                // Select first slide by default if available
                const firstSlide = data.files.find((f: string) => f.toLowerCase().includes('slide') && f.endsWith('.tsx'));
                if (firstSlide && !selectedFile) {
                    handleFileSelect(firstSlide);
                }
            }
        } catch (e) {
            console.error("Failed to fetch artifacts", e);
        }
    };

    // Helper to clean up content causing "type: text" issues
    const parseContent = (raw: string) => {
        if (!raw) return "";
        try {
            const parsed = JSON.parse(raw);
            if (parsed.text) return parsed.text;
            if (parsed.content) return parsed.content;
            return raw;
        } catch (e) {
            if (raw.trim().startsWith("{") && raw.includes("'type': 'text'")) {
                try {
                    const jsonFriendly = raw.replace(/'/g, '"').replace(/True/g, 'true').replace(/False/g, 'false');
                    const parsed = JSON.parse(jsonFriendly);
                    if (parsed.text) return parsed.text;
                } catch (err) {
                    const textMatch = raw.match(/'text':\s*'((?:[^'\\]|\\.)*)'/);
                    if (textMatch && textMatch[1]) {
                        return textMatch[1]
                            .replace(/\\n/g, '\n')
                            .replace(/\\'/g, "'")
                            .replace(/\\"/g, '"');
                    }
                }
            }
            return raw.replace(/\\n/g, '\n').replace(/\\t/g, '  ').replace(/\\'/g, "'").replace(/\\"/g, '"');
        }
    };

    const handleFileSelect = async (filename: string) => {
        setLoading(true);
        setSelectedFile(filename);
        try {
            const res = await fetch(`http://localhost:8000/api/artifacts/${filename}?thread_id=${threadId}`);
            const data = await res.json();
            if (data.content) {
                const cleanContent = parseContent(data.content);
                setFileContent(cleanContent);
            }
        } catch (e) {
            console.error("Failed to read file", e);
        } finally {
            setLoading(false);
        }
    };

    const handleExportPdf = async () => {
        if (!selectedFile) return;
        setLoading(true);
        try {
            const res = await fetch(`http://localhost:8000/api/artifacts/export-pdf`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: selectedFile, thread_id: threadId })
            });

            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = selectedFile.replace(/\.(md|mdx|txt)$/i, '') + "_Final.pdf";
                document.body.appendChild(a);
                a.click();
                a.remove();
            } else {
                alert("PDF Export failed. Check backend logs.");
            }
        } catch (e) {
            console.error("Export error", e);
            alert("Error exporting PDF");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchFiles();
    }, []);

    return (
        <div className="absolute inset-0 z-50 bg-black/95 flex text-cyber-text font-mono">
            {/* Sidebar: File List */}
            <div className="w-80 border-r border-cyber-border bg-slate-900/50 flex flex-col">
                <div className="p-4 border-b border-cyber-border flex justify-between items-center">
                    <h2 className="font-bold text-neon-pink flex items-center gap-2">
                        <LayoutTemplate size={18} /> ARTIFACTS
                    </h2>
                    <button onClick={fetchFiles} className="hover:text-white transition-colors">
                        <RefreshCw size={16} />
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {files.map(f => (
                        <button
                            key={f}
                            onClick={() => handleFileSelect(f)}
                            className={`w-full text-left px-3 py-2 rounded text-xs truncate flex items-center gap-2 transition-all ${selectedFile === f
                                ? 'bg-cyber-primary/20 text-cyber-primary border border-cyber-primary/50'
                                : 'hover:bg-slate-800 text-slate-400'
                                }`}
                        >
                            <FileText size={14} />
                            {f}
                        </button>
                    ))}
                </div>
                <div className="p-4 border-t border-cyber-border">
                    <button
                        onClick={onClose}
                        className="w-full py-2 bg-slate-800 hover:bg-slate-700 rounded text-center text-xs"
                    >
                        CLOSE VIEWER
                    </button>
                </div>
            </div>

            {/* Main Area: Preview */}
            <div className="flex-1 flex flex-col relative">
                {selectedFile && (
                    <div className="absolute top-4 right-4 z-50 flex gap-2">
                        {selectedFile.endsWith('.md') && (
                            <button
                                onClick={handleExportPdf}
                                className="bg-neon-pink/20 hover:bg-neon-pink/40 text-neon-pink px-4 py-2 rounded border border-neon-pink/50 backdrop-blur flex items-center gap-2 text-xs font-bold transition-all"
                            >
                                <Download size={14} /> EXPORT PDF
                            </button>
                        )}
                        <div className="bg-black/50 px-4 py-2 rounded border border-cyber-border backdrop-blur">
                            <span className="text-neon-green text-xs">{selectedFile}</span>
                        </div>
                    </div>
                )}

                {loading ? (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="animate-spin w-8 h-8 border-2 border-cyber-primary border-t-transparent rounded-full" />
                    </div>
                ) : (
                    <div className="flex-1 overflow-hidden">
                        {/* If it's a TSX file, render with SlidePreview. */}

                        {/* If it's a TSX file, render with SlidePreview. */}
                        {/* If it's a MD file, render with MarkdownPreview (Report View). */}
                        {selectedFile?.endsWith('.tsx') ? (
                            <SlidePreview code={fileContent} />
                        ) : selectedFile?.endsWith('.md') ? (
                            <MarkdownPreview content={fileContent} />
                        ) : (
                            <pre className="p-8 text-xs text-slate-300 overflow-auto h-full font-mono whitespace-pre-wrap">
                                {fileContent}
                            </pre>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
