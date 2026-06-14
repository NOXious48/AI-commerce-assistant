import { useState } from 'react';
import Sidebar from '../components/Sidebar';
import ProductPanel from '../components/ProductPanel';
import ChatPanel from '../components/ChatPanel';
import CartPanel from '../components/CartPanel';
import ProductDetailsModal from '../components/ProductDetailsModal';

export default function Dashboard() {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [consultationState, setConsultationState] = useState<any>({});
  const [filteringMetadata, setFilteringMetadata] = useState<any>({});
  const [cartItems, setCartItems] = useState<any[]>([]);
  const [cartWorkspace, setCartWorkspace] = useState<any>({});
  const [selectedProduct, setSelectedProduct] = useState<any | null>(null);
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
        filteringMetadata={filteringMetadata}
        onProductClick={(product) => setSelectedProduct(product)}
      />

      {/* Right Panel: Chat (40%) */}
      <ChatPanel 
        sessionId={currentSessionId}
        onSessionCreated={setCurrentSessionId}
        onProductsReceived={setProducts}
        onStateReceived={setConsultationState}
        onMetricsReceived={setFilteringMetadata}
        onCartReceived={setCartItems}
        onCartWorkspaceReceived={setCartWorkspace}
        isTyping={isTyping}
        setIsTyping={setIsTyping}
      />
      
      {/* Absolute Overlays */}
      <CartPanel 
        sessionId={currentSessionId} 
        cartItems={cartItems} 
        setCartItems={setCartItems}
        cartWorkspace={cartWorkspace}
      />
      
      {selectedProduct && (
        <ProductDetailsModal
          sessionId={currentSessionId}
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
          cartItems={cartItems}
          setCartItems={setCartItems}
        />
      )}
    </div>
  );
}
