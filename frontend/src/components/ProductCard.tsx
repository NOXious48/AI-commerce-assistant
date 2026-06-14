import React, { useState } from 'react';
import { Heart, Star, GitCompare, ShoppingCart, Sparkles, Plus, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';

interface ProductCardProps {
  product: any;
  sessionId?: string; // For deep-linking
  domain?: string;
  planId?: string;
}

export default function ProductCard({ product, sessionId, domain, planId }: ProductCardProps) {
  const { authFetch } = useAuth();
  const { addToCart } = useCart();
  const queryClient = useQueryClient();
  const [isSaved, setIsSaved] = useState(false); 
  
  // Temporary States
  const [isAddingToCart, setIsAddingToCart] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [quantity, setQuantity] = useState(1);

  const toggleSaveMutation = useMutation({
    mutationFn: async () => {
      if (isSaved) {
        await authFetch(`/api/user/saved-products/${product.parent_asin}`, { method: 'DELETE' });
      } else {
        await authFetch('/api/user/saved-products', {
          method: 'POST',
          body: JSON.stringify({ parent_asin: product.parent_asin })
        });
      }
    },
    onMutate: () => {
      setIsSaved(!isSaved); 
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-products'] });
    },
    onError: () => {
      setIsSaved(isSaved); // rollback
      // Toast error should be shown here
    }
  });

  const addToCompareMutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch('/api/user/compare', { 
        method: 'POST', 
        body: JSON.stringify({ parent_asin: product.parent_asin }) 
      });
      if (!res.ok) throw new Error("Failed to add to compare");
      return res.json();
    },
    onMutate: () => setIsComparing(true),
    onSuccess: () => {
      setIsComparing(false);
      // Toast success
    },
    onError: () => {
      setIsComparing(false);
      // Toast error
    }
  });

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsAddingToCart(true);
    try {
      await addToCart(product.parent_asin, quantity);
    } finally {
      setIsAddingToCart(false);
    }
  };

  const handleAskAI = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    window.dispatchEvent(new CustomEvent('open-ai-drawer', { 
      detail: { prompt: `Can you tell me more about ${product.title}?` } 
    }));
  };

  const handleAddToPlan = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    window.dispatchEvent(new CustomEvent('open-ai-drawer', { 
      detail: { prompt: `Add ${product.title} to my active plan.` } 
    }));
  };

  const renderStars = (rating: number) => {
    return (
      <div className="flex items-center text-yellow-500">
        {[...Array(5)].map((_, i) => (
          <Star key={i} size={14} fill={i < Math.floor(rating) ? "currentColor" : "none"} strokeWidth={i < Math.floor(rating) ? 0 : 1} />
        ))}
        <span className="text-xs text-blue-500 ml-1 hover:underline cursor-pointer">{product.rating_number?.toLocaleString() || 0}</span>
      </div>
    );
  };

  const imageUrl = product.image_url ? `/api/image-proxy?url=${encodeURIComponent(product.image_url)}` : '';
  
  // Construct deep-link URL
  let productUrl = `/product/${product.parent_asin}`;
  const queryParams = new URLSearchParams();
  if (sessionId) queryParams.append('session', sessionId);
  if (domain) queryParams.append('domain', domain);
  if (planId) queryParams.append('plan', planId);
  if (queryParams.toString()) productUrl += `?${queryParams.toString()}`;

  return (
    <div className="bg-white rounded p-4 flex flex-col h-full border border-gray-200 hover:shadow-lg transition-shadow relative group">
      <button 
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggleSaveMutation.mutate(); }}
        className={`absolute top-2 left-2 p-1.5 bg-white/80 backdrop-blur-sm rounded-full z-10 transition-colors shadow-sm
          ${isSaved ? 'text-red-500' : 'text-gray-400 hover:text-red-500'}`}
      >
        <Heart size={16} fill={isSaved ? "currentColor" : "none"} />
      </button>

      <Link to={productUrl} className="flex-1 flex flex-col">
        <div className="h-48 flex items-center justify-center mb-4 relative overflow-hidden">
          {imageUrl ? (
            <img src={imageUrl} alt={product.title} className="max-w-full max-h-full object-contain mix-blend-multiply group-hover:scale-105 transition-transform duration-300" />
          ) : (
            <div className="text-gray-400">No Image</div>
          )}
        </div>

        <div className="flex-1 flex flex-col">
          <h4 className="text-sm text-gray-900 line-clamp-2 hover:text-orange-600 mb-1">
            {product.title}
          </h4>
          
          <div className="mb-1">
            {renderStars(product.average_rating || 0)}
          </div>
          
          <div className="text-xl font-medium text-gray-900 mb-2">
            <span className="text-sm font-normal align-top">$</span>
            {Math.floor(product.price || 0)}
            <span className="text-sm font-normal align-top">
              {((product.price || 0) % 1).toFixed(2).substring(1)}
            </span>
          </div>

          <div className="text-xs text-gray-500 mb-3 truncate">
            {product.brand ? `Brand: ${product.brand}` : (product.store ? `Store: ${product.store}` : 'Amazon')}
          </div>
        </div>
      </Link>

      <div className="mt-auto pt-3 border-t border-gray-100 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <div className="flex items-center border border-gray-300 rounded-full overflow-hidden" onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); setQuantity(q => Math.max(1, q - 1)); }}
              className="px-2 py-1 text-sm font-bold text-gray-600 hover:bg-gray-100 transition-colors"
            >
              −
            </button>
            <span className="px-2 text-xs font-medium text-gray-800 min-w-[20px] text-center">{quantity}</span>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); setQuantity(q => Math.min(10, q + 1)); }}
              className="px-2 py-1 text-sm font-bold text-gray-600 hover:bg-gray-100 transition-colors"
            >
              +
            </button>
          </div>
          <button 
            onClick={handleAddToCart}
            disabled={isAddingToCart}
            className="flex-1 bg-[#FFD814] hover:bg-[#F7CA00] text-[#0F1111] text-xs font-semibold py-2 rounded-full flex items-center justify-center gap-1 transition-colors disabled:opacity-70 border border-[#FCD200]"
          >
            {isAddingToCart ? <Loader2 size={14} className="animate-spin" /> : <ShoppingCart size={14} />} 
            {isAddingToCart ? 'Adding...' : 'Add to Cart'}
          </button>
        </div>
        
        <div className="flex gap-2">
          <button 
            onClick={handleAskAI}
            className="flex-1 bg-[#131921] hover:bg-[#232f3e] text-white text-xs font-semibold py-2 rounded-full flex items-center justify-center gap-1 transition-colors shadow-sm"
          >
            <Sparkles size={14} className="text-[#FF9900]" /> Ask AI
          </button>
        </div>
        
        <div className="flex gap-2">
          <button 
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); addToCompareMutation.mutate(); }}
            disabled={isComparing}
            className="flex-1 border border-gray-300 bg-white hover:bg-gray-50 text-[#0F1111] text-xs font-medium py-1.5 rounded-full flex items-center justify-center gap-1 transition-colors disabled:opacity-70"
          >
            {isComparing ? <Loader2 size={12} className="animate-spin" /> : <GitCompare size={12} />} 
            {isComparing ? 'Comparing...' : 'Compare'}
          </button>

          <button 
            onClick={handleAddToPlan}
            className="flex-1 border border-gray-300 bg-white hover:bg-gray-50 text-[#0F1111] text-xs font-medium py-1.5 rounded-full flex items-center justify-center gap-1 transition-colors"
          >
            <Plus size={12} /> Add to Plan
          </button>
        </div>
      </div>
    </div>
  );
}
