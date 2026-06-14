import React, { useState } from 'react';
import { ShoppingCart, X, Plus, Minus, Trash2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface CartPanelProps {
  sessionId: string | null;
  cartItems: any[];
  setCartItems: (items: any[]) => void;
}

export default function CartPanel({ sessionId, cartItems, setCartItems }: CartPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { authFetch } = useAuth();

  const totalItems = cartItems.reduce((acc, item) => acc + item.quantity, 0);
  const subtotal = cartItems.reduce((acc, item) => acc + (item.price * item.quantity), 0).toFixed(2);

  if (cartItems.length === 0) return null;

  const handleUpdateQuantity = async (productId: string, delta: number, currentQty: number) => {
    if (!sessionId) return;
    if (currentQty + delta <= 0) {
      handleRemove(productId, true);
      return;
    }

    try {
      if (delta > 0) {
        await authFetch('/api/cart/add', {
          method: 'POST',
          body: JSON.stringify({ session_id: sessionId, product_id: productId, quantity: delta })
        });
        // Optimistic update
        setCartItems(cartItems.map(i => i.product_id === productId ? { ...i, quantity: i.quantity + delta } : i));
      } else {
        await authFetch('/api/cart/remove', {
          method: 'POST',
          body: JSON.stringify({ session_id: sessionId, product_id: productId, fully_remove: false })
        });
        setCartItems(cartItems.map(i => i.product_id === productId ? { ...i, quantity: i.quantity - 1 } : i));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRemove = async (productId: string, fullyRemove: boolean = true) => {
    if (!sessionId) return;
    try {
      await authFetch('/api/cart/remove', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId, product_id: productId, fully_remove: fullyRemove })
      });
      setCartItems(cartItems.filter(i => i.product_id !== productId));
    } catch (e) {
      console.error(e);
    }
  };

  const handleClear = async () => {
    if (!sessionId) return;
    try {
      await authFetch('/api/cart/clear', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId })
      });
      setCartItems([]);
      setIsExpanded(false);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className={`fixed bottom-0 left-[20%] right-[40%] bg-bg-card border-t border-l border-border-light shadow-2xl transition-all duration-300 z-40 rounded-tl-xl overflow-hidden flex flex-col ${isExpanded ? 'h-[60vh]' : 'h-14 cursor-pointer hover:bg-bg-secondary'}`}>
      
      {/* Header (Collapsed View) */}
      <div 
        className="h-14 px-6 flex items-center justify-between shrink-0 select-none"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <div className="relative">
            <ShoppingCart size={20} className="text-accent-light" />
            <div className="absolute -top-2 -right-2 bg-accent text-white text-[10px] w-4 h-4 rounded-full flex items-center justify-center font-bold">
              {totalItems}
            </div>
          </div>
          <span className="font-semibold text-text-primary text-sm">
            Cart ({totalItems} Items) <span className="text-text-muted px-2">•</span> <span className="text-green-400">${subtotal}</span>
          </span>
        </div>
        <div>
          {isExpanded ? (
            <X size={18} className="text-text-muted hover:text-white transition-colors" />
          ) : (
            <div className="text-xs font-semibold text-accent-light bg-accent/10 px-3 py-1 rounded-full hover:bg-accent/20 transition-colors">
              View Cart
            </div>
          )}
        </div>
      </div>

      {/* Expanded Content */}
      <div className={`flex-1 flex flex-col overflow-hidden transition-opacity duration-300 ${isExpanded ? 'opacity-100' : 'opacity-0'}`}>
        <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-custom bg-bg-primary">
          {cartItems.map((item) => (
            <div key={item.product_id} className="flex items-center gap-4 bg-bg-card p-3 rounded-lg border border-border-light">
              {item.image ? (
                <img src={item.image} alt={item.title} className="w-16 h-16 object-contain rounded bg-white p-1" />
              ) : (
                <div className="w-16 h-16 bg-bg-secondary rounded flex items-center justify-center">No Image</div>
              )}
              
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-text-primary truncate">{item.title}</h4>
                <div className="text-sm text-green-400 font-bold mt-1">${item.price}</div>
              </div>

              <div className="flex flex-col items-end gap-2 shrink-0">
                <button 
                  onClick={() => handleRemove(item.product_id, true)}
                  className="text-text-muted hover:text-red-400 transition-colors p-1"
                >
                  <Trash2 size={14} />
                </button>
                <div className="flex items-center gap-3 bg-bg-secondary rounded-lg px-2 py-1">
                  <button onClick={() => handleUpdateQuantity(item.product_id, -1, item.quantity)} className="text-text-muted hover:text-white"><Minus size={14} /></button>
                  <span className="text-xs font-bold w-4 text-center">{item.quantity}</span>
                  <button onClick={() => handleUpdateQuantity(item.product_id, 1, item.quantity)} className="text-text-muted hover:text-white"><Plus size={14} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-border-light bg-bg-card">
          <div className="flex justify-between items-center mb-4">
            <span className="text-sm text-text-muted font-medium">Subtotal</span>
            <span className="text-xl font-bold text-text-primary">${subtotal}</span>
          </div>
          <div className="flex gap-3">
            <button 
              onClick={handleClear}
              className="px-4 py-2 text-sm font-semibold text-text-muted hover:text-white hover:bg-bg-secondary rounded-lg transition-colors border border-border-light"
            >
              Clear Cart
            </button>
            <button className="flex-1 px-4 py-2 bg-gradient-to-r from-accent to-orange-500 hover:from-accent-light hover:to-orange-400 text-white text-sm font-bold rounded-lg shadow-lg shadow-accent/20 transition-all opacity-50 cursor-not-allowed">
              Checkout (Coming Soon)
            </button>
          </div>
        </div>
      </div>

    </div>
  );
}
