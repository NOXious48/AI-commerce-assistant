import React, { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './AuthContext';

interface CartContextType {
  cartItems: any[];
  sessionId: string | null;
  loading: boolean;
  lastAddedItem: any | null;
  addToCart: (productId: string, quantity?: number) => Promise<void>;
  removeFromCart: (productId: string, fullyRemove?: boolean) => Promise<void>;
  clearCart: () => Promise<void>;
  refreshCart: () => Promise<void>;
  clearLastAddedItem: () => void;
  syncCart: (newCartItems: any[]) => void;
}

const CartContext = createContext<CartContextType | null>(null);

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { authFetch, user } = useAuth();
  const [cartItems, setCartItems] = useState<any[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [lastAddedItem, setLastAddedItem] = useState<any>(null);

  const refreshCart = async () => {
    if (!sessionId) return;
    try {
      const sessRes = await authFetch(`/api/chat/session/${sessionId}`);
      if (sessRes.ok) {
        const data = await sessRes.json();
        setCartItems(data.cart_items || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const clearLastAddedItem = () => setLastAddedItem(null);

  // Initialize session and fetch cart
  useEffect(() => {
    if (!user) {
      setCartItems([]);
      setLoading(false);
      return;
    }

    const initCart = async () => {
      try {
        setLoading(true);
        // 1. Get History to find active session
        const histRes = await authFetch('/api/chat/history');
        if (!histRes.ok) throw new Error('Failed to fetch history');
        const sessions = await histRes.json();
        
        let activeId = null;
        if (sessions && sessions.length > 0) {
          activeId = sessions[0].session_id;
        } else {
          // 2. Create session if none exists
          const createRes = await authFetch('/api/chat/new-session', { method: 'POST' });
          if (!createRes.ok) throw new Error('Failed to create session');
          const newSession = await createRes.json();
          activeId = newSession.session_id;
        }
        
        setSessionId(activeId);

        // 3. Fetch session data to get cart items
        if (activeId) {
          const sessRes = await authFetch(`/api/chat/session/${activeId}`);
          if (sessRes.ok) {
            const data = await sessRes.json();
            setCartItems(data.cart_items || []);
          }
        }
      } catch (err) {
        console.error("Cart init error:", err);
      } finally {
        setLoading(false);
      }
    };

    initCart();
  }, [user, authFetch]);

  const syncCart = (newCartItems: any[]) => {
    // Check if any item was added
    const newItems = newCartItems.filter(
      (n: any) => !cartItems.some((c: any) => c.parent_asin === n.parent_asin && c.quantity >= n.quantity)
    );
    
    setCartItems(newCartItems);
    
    if (newItems.length > 0) {
      setLastAddedItem({ ...newItems[0], timestamp: Date.now() });
    }
  };

  const addToCart = async (productId: string, quantity: number = 1) => {
    if (!sessionId) return;
    try {
      const res = await authFetch('/api/cart/add', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId, product_id: productId, quantity })
      });
      if (res.ok) {
        const data = await res.json();
        setCartItems(data.cart_items);
        
        // Find the added item and trigger the popup
        const added = data.cart_items.find((i: any) => i.parent_asin === productId);
        if (added) {
          setLastAddedItem({ ...added, timestamp: Date.now() });
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const removeFromCart = async (productId: string, fullyRemove: boolean = false) => {
    if (!sessionId) return;
    try {
      const res = await authFetch('/api/cart/remove', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId, product_id: productId, fully_remove: fullyRemove })
      });
      if (res.ok) {
        const data = await res.json();
        setCartItems(data.cart_items);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const clearCart = async () => {
    if (!sessionId) return;
    try {
      const res = await authFetch('/api/cart/clear', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId })
      });
      if (res.ok) {
        setCartItems([]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <CartContext.Provider value={{ cartItems, sessionId, loading, addToCart, removeFromCart, clearCart, refreshCart, lastAddedItem, clearLastAddedItem, syncCart }}>
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
};
