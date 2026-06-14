import { useState } from 'react';
import Sidebar from '../components/Sidebar';
import ProductPanel from '../components/ProductPanel';
import ChatPanel from '../components/ChatPanel';

export default function Dashboard() {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [consultationState, setConsultationState] = useState<any>({});
  const [isTyping, setIsTyping] = useState(false);

  return (
    <div className="flex h-screen bg-bg-primary overflow-hidden">
      {/* Left Panel: Chat History (20%) */}
      <Sidebar 
        currentSessionId={currentSessionId} 
        onSelectSession={setCurrentSessionId} 
      />

      {/* Center Panel: Product Results (40%) */}
      <ProductPanel 
        products={products} 
        isLoading={isTyping}
        consultationState={consultationState}
      />

      {/* Right Panel: Chat (40%) */}
      <ChatPanel 
        sessionId={currentSessionId}
        onSessionCreated={setCurrentSessionId}
        onProductsReceived={setProducts}
        onStateReceived={setConsultationState}
        isTyping={isTyping}
        setIsTyping={setIsTyping}
      />
    </div>
  );
}
