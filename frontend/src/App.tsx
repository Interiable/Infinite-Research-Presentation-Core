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

  const { logs, currentSlideCode, sendMessage, sendCommand, isConnected } = useAgentWebSocket(wsUrl, threadId);

  return (
    <div className="flex h-screen w-screen bg-cyber-dark text-cyber-text overflow-hidden font-sans">

      {/* Left Panel: Communication & Control (30%) */}
      <div className="w-[30%] flex flex-col border-r border-cyber-border z-10 shadow-xl">
        <ChatPanel
          onSendMessage={sendMessage}
          onSendCommand={sendCommand}
          isConnected={isConnected}
          logs={logs}
          threadId={threadId}
          onNewSession={handleNewSession}
        />
        <Terminal logs={logs} />
      </div>

      {/* Right Panel: Infinite Preview (70%) */}
      <div className="w-[70%] relative bg-black">
        {/* Artifact Viewer Toggle */}
        <button
          onClick={() => setShowArtifacts(true)}
          className="absolute top-4 right-4 z-40 p-2 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded text-xs text-cyber-text transition-all"
        >
          📂 OPEN ARTIFACT VIEWER
        </button>

        {showArtifacts && <ArtifactViewer onClose={() => setShowArtifacts(false)} />}

        <SlidePreview code={currentSlideCode} />
      </div>

    </div>
  );
}

export default App;
