import { useAgentWebSocket } from './hooks/useAgentWebSocket';
import { ChatPanel } from './components/ChatPanel';
import { Terminal } from './components/Terminal';
import { SlidePreview } from './components/SlidePreview';

function App() {
  // Connect to our Backend WebSocket
  // Connect to our Backend WebSocket dynamically
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/api/ws`;

  const { logs, currentSlideCode, sendMessage, isConnected } = useAgentWebSocket(wsUrl);

  return (
    <div className="flex h-screen w-screen bg-cyber-dark text-cyber-text overflow-hidden font-sans">

      {/* Left Panel: Communication & Control (30%) */}
      <div className="w-[30%] flex flex-col border-r border-cyber-border z-10 shadow-xl">
        <ChatPanel onSendMessage={sendMessage} isConnected={isConnected} />
        <Terminal logs={logs} />
      </div>

      {/* Right Panel: Infinite Preview (70%) */}
      <div className="w-[70%] relative bg-black">
        <SlidePreview code={currentSlideCode} />
      </div>

    </div>
  );
}

export default App;
