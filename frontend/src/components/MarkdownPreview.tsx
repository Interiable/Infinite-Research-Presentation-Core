import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownPreviewProps {
    content: string;
}

export const MarkdownPreview: React.FC<MarkdownPreviewProps> = ({ content }) => {
    return (
        <div className="h-full overflow-y-auto bg-cyber-dark p-8 md:p-12">
            <div className="max-w-4xl mx-auto">
                <article className="prose prose-invert prose-lg prose-slate max-w-none
                    prose-headings:text-neon-pink prose-headings:font-bold
                    prose-a:text-neon-blue prose-a:no-underline hover:prose-a:underline
                    prose-strong:text-white prose-code:text-neon-green
                    prose-pre:bg-cyber-panel prose-pre:border prose-pre:border-cyber-border
                    prose-li:marker:text-neon-green
                ">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {content}
                    </ReactMarkdown>
                </article>
            </div>
        </div>
    );
};
