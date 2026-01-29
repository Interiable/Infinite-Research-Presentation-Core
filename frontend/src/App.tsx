import { useAgentWebSocket } from './hooks/useAgentWebSocket';
import { ChatPanel } from './components/ChatPanel';
import { Terminal } from './components/Terminal';
import { SlidePreview } from './components/SlidePreview';

function App() {
  // Connect to our Backend WebSocket
  const { logs, currentSlideCode, sendMessage, isConnected } = useAgentWebSocket('ws://localhost:8000/api/ws');

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
