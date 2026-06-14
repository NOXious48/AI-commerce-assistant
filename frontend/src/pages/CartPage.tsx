import React from 'react';
import { useCart } from '../context/CartContext';
import { Minus, Plus, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function CartPage() {
  const { cartItems, loading, addToCart, removeFromCart, clearCart } = useCart();

  const totalItems = cartItems.reduce((acc, item) => acc + item.quantity, 0);
  const subtotal = cartItems.reduce((acc, item) => acc + ((item.price || 0) * item.quantity), 0).toFixed(2);

  const handleUpdateQuantity = async (productId: string, delta: number, currentQty: number) => {
    if (delta > 0) {
      await addToCart(productId, 1);
    } else {
      await removeFromCart(productId, false);
    }
  };

  const handleRemove = async (productId: string) => {
    await removeFromCart(productId, true);
  };

  if (loading) {
    return <div className="p-8 text-center">Loading cart...</div>;
  }

  return (
    <div className="bg-gray-100 min-h-screen py-8">
      <div className="max-w-screen-xl mx-auto px-4 grid grid-cols-1 lg:grid-cols-4 gap-8">
        
        {/* Cart Items List */}
        <div className="lg:col-span-3 bg-white p-6 rounded shadow">
          <h1 className="text-3xl font-normal text-gray-900 mb-2">Shopping Cart</h1>
          <p className="text-sm text-blue-600 hover:underline cursor-pointer mb-4">Deselect all items</p>
          <div className="text-right text-sm text-gray-500 mb-2">Price</div>
          <hr className="border-gray-300 mb-4" />

          {cartItems.length === 0 ? (
            <div className="py-8">
              <h2 className="text-xl font-medium mb-4">Your Amazon Cart is empty.</h2>
              <Link to="/" className="text-blue-600 hover:underline">Continue shopping</Link>
            </div>
          ) : (
            <div className="space-y-6">
              {cartItems.map(item => (
                <div key={item.product_id} className="flex gap-4 border-b border-gray-200 pb-4">
                  <div className="w-32 h-32 shrink-0">
                    <img src={item.image} alt={item.title} className="w-full h-full object-contain mix-blend-multiply" />
                  </div>
                  <div className="flex-1">
                    <div className="flex justify-between">
                      <Link to={`/product/${item.product_id}`} className="text-lg text-gray-900 font-medium hover:text-orange-600 line-clamp-2">
                        {item.title}
                      </Link>
                      <div className="text-lg font-bold text-gray-900 ml-4">${item.price?.toFixed(2)}</div>
                    </div>
                    
                    {/* Cart Workspace Metadata Visualization */}
                    <div className="my-2 bg-gray-50 border border-gray-100 rounded p-2 text-xs">
                      {item.added_by === 'ai' ? (
                        <div className="text-purple-700 font-medium">✨ Added by AI</div>
                      ) : (
                        <div className="text-gray-600 font-medium">👤 Added by User</div>
                      )}
                      
                      {item.reason && (
                        <div className="text-gray-500 mt-0.5">Reason: {item.reason}</div>
                      )}
                      
                      {(import.meta.env.VITE_DEMO_MODE === 'true' || import.meta.env.MODE === 'development') && (
                        <div className="mt-1 pt-1 border-t border-gray-200 text-[10px] font-mono text-gray-400">
                          {item.domain && <span>Domain: {item.domain} | </span>}
                          {item.plan_id && <span>Plan: {item.plan_id}</span>}
                        </div>
                      )}
                    </div>
                    
                    <div className="text-green-600 text-xs my-1">In Stock</div>
                    <div className="text-xs text-gray-500 mb-2">Eligible for FREE Shipping</div>
                    
                    <div className="flex items-center gap-4 mt-4">
                      <div className="flex items-center border border-gray-300 rounded-md overflow-hidden bg-gray-100 shadow-sm">
                        <button onClick={() => handleUpdateQuantity(item.product_id, -1, item.quantity)} className="px-3 py-1 hover:bg-gray-200"><Minus size={14}/></button>
                        <span className="px-3 py-1 bg-white border-x border-gray-300 text-sm">{item.quantity}</span>
                        <button onClick={() => handleUpdateQuantity(item.product_id, 1, item.quantity)} className="px-3 py-1 hover:bg-gray-200"><Plus size={14}/></button>
                      </div>
                      <div className="text-gray-300">|</div>
                      <button onClick={() => handleRemove(item.product_id)} className="text-xs text-blue-600 hover:underline">Delete</button>
                      <div className="text-gray-300">|</div>
                      <button className="text-xs text-blue-600 hover:underline">Save for later</button>
                    </div>
                  </div>
                </div>
              ))}
              
              <div className="text-right pt-2">
                <span className="text-lg font-medium text-gray-900">Subtotal ({totalItems} items): </span>
                <span className="text-lg font-bold text-gray-900">${subtotal}</span>
              </div>
            </div>
          )}
        </div>

        {/* Checkout Summary */}
        <div className="lg:col-span-1">
          <div className="bg-white p-6 rounded shadow mb-4">
            <div className="text-lg font-medium text-gray-900 mb-4">
              Subtotal ({totalItems} items): <span className="font-bold">${subtotal}</span>
            </div>
            <button className="w-full bg-yellow-400 hover:bg-yellow-500 text-black py-2 rounded-full font-medium shadow-sm transition-colors text-sm">
              Proceed to checkout
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
