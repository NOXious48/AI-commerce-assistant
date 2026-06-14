import React, { useEffect, useState } from 'react';
import { useCart } from '../context/CartContext';
import { CheckCircle2, X } from 'lucide-react';
import { Link } from 'react-router-dom';

const CartPopup = () => {
  const { lastAddedItem, clearLastAddedItem } = useCart();
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (lastAddedItem) {
      setIsVisible(true);
      
      const timer = setTimeout(() => {
        setIsVisible(false);
      }, 4000);

      // We don't clear the item immediately to allow the slide-out animation to show the item
      return () => clearTimeout(timer);
    }
  }, [lastAddedItem]);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(clearLastAddedItem, 300); // wait for animation
  };

  if (!lastAddedItem) return null;

  return (
    <div 
      className={`fixed top-24 left-4 z-50 transition-all duration-500 ease-in-out transform ${
        isVisible ? 'translate-x-0 opacity-100' : '-translate-x-[150%] opacity-0'
      }`}
    >
      <div className="bg-white rounded-lg shadow-2xl border border-green-100 w-80 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-green-50 px-4 py-3 flex items-center justify-between border-b border-green-100">
          <div className="flex items-center gap-2 text-green-700 font-bold">
            <CheckCircle2 size={20} className="text-green-600" />
            <span>Added to Cart</span>
          </div>
          <button 
            onClick={handleClose} 
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 flex gap-4">
          <div className="w-16 h-16 shrink-0 bg-gray-50 rounded-md p-1 border border-gray-100 flex items-center justify-center">
            {lastAddedItem.image ? (
              <img 
                src={lastAddedItem.image} 
                alt={lastAddedItem.title} 
                className="max-w-full max-h-full object-contain mix-blend-multiply" 
              />
            ) : (
              <div className="text-gray-300 text-xs text-center">No image</div>
            )}
          </div>
          <div className="flex-1 flex flex-col justify-center">
            <h4 className="text-sm font-medium text-gray-900 line-clamp-2 leading-tight">
              {lastAddedItem.title}
            </h4>
            <div className="text-sm font-bold text-gray-900 mt-1">
              ${(lastAddedItem.price || 0).toFixed(2)}
            </div>
            {lastAddedItem.quantity > 1 && (
              <div className="text-xs text-gray-500 mt-0.5">
                Qty: {lastAddedItem.quantity}
              </div>
            )}
          </div>
        </div>

        {/* Action */}
        <div className="px-4 pb-4">
          <Link 
            to="/cart" 
            onClick={handleClose}
            className="block w-full bg-yellow-400 hover:bg-yellow-500 text-center text-black py-2 rounded-full font-medium shadow-sm transition-colors text-sm"
          >
            View Cart & Checkout
          </Link>
        </div>
      </div>
    </div>
  );
};

export default CartPopup;
