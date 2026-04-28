import React, { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import ConfigScreen from './components/ConfigScreen';
import ChatInterface from './components/ChatInterface';

function App() {
  const [sessionId, setSessionId] = useState(null);

  return (
    <AnimatePresence mode="wait">
      {!sessionId ? (
        <ConfigScreen key="config" onConfigure={setSessionId} />
      ) : (
        <ChatInterface key="chat" sessionId={sessionId} onDisconnect={() => setSessionId(null)} />
      )}
    </AnimatePresence>
  );
}

export default App;
