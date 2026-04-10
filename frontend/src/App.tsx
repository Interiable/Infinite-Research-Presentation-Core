import { useState } from 'react';
import { useAgentWebSocket } from './hooks/useAgentWebSocket';
import { ChatPanel } from './components/ChatPanel';
import { Terminal } from './components/Terminal';
import { SlidePreview } from './components/SlidePreview';
import { ArtifactViewer } from './components/ArtifactViewer';

function App() {
  const [showArtifacts, setShowArtifacts] = useState(false);
  // Connect to our Backend WebSocket
  // Session Management
  const [threadId, setThreadId] = useState<string>(() => {
    // Persist session across reloads
    return localStorage.getItem('agent_thread_id') || Math.random().toString(36).substring(7);
  });

  const handleNewSession = () => {
    const newId = Math.random().toString(36).substring(7);
    localStorage.setItem('agent_thread_id', newId);
    setThreadId(newId);
  };

  // Connect to our Backend WebSocket dynamically
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/api/ws`;

  const { logs, dialogue, currentSlideCode, progress, sendMessage, sendCommand, isConnected } = useAgentWebSocket(wsUrl, threadId);

  return (
    <div className="flex flex-col md:flex-row h-[100dvh] w-[100dvw] bg-cyber-dark text-cyber-text overflow-hidden font-sans">

      {/* Left Panel: Communication & Control (Responsive: 50% height on mobile, 30% width on tablet/desktop) */}
      <div className="w-full md:w-[30%] lg:w-[25%] flex flex-col border-b md:border-b-0 md:border-r border-cyber-border z-10 shadow-xl h-[45%] md:h-full shrink-0">
        <div className="flex-1 min-h-0 overflow-hidden">
          <ChatPanel
            onSendMessage={sendMessage}
            onSendCommand={sendCommand}
            isConnected={isConnected}
            logs={logs}
            dialogue={dialogue || []} // Pass dialogue state
            threadId={threadId}
            onNewSession={handleNewSession}
          />
        </div>
        <Terminal logs={logs} />
      </div>

      {/* Right Panel: Infinite Preview (Responsive: 55% height on mobile, 70% width on tablet/desktop) */}
      <div className="w-full md:w-[70%] lg:w-[75%] relative bg-black flex-1 min-h-0">
        {/* Artifact Viewer Toggle */}
        <button
          onClick={() => setShowArtifacts(true)}
          className="absolute top-2 right-2 md:top-4 md:right-4 z-40 p-1.5 md:p-2 bg-slate-800/80 hover:bg-slate-700 border border-slate-600 rounded text-[10px] md:text-xs text-cyber-text transition-all backdrop-blur-sm"
        >
          📂 OPEN ARTIFACT VIEWER
        </button>

        {showArtifacts && <ArtifactViewer onClose={() => setShowArtifacts(false)} threadId={threadId} />}

        <SlidePreview code={currentSlideCode} progress={progress} />
      </div>

    </div>
  );
}

export default App;
