import React, { useState } from 'react';
import { Heart, ShoppingBag, Star } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useMutation, useQueryClient } from '@tanstack/react-query';

interface ProductCardProps {
  product: any;
}

export default function ProductCard({ product }: ProductCardProps) {
  const { authFetch } = useAuth();
  const queryClient = useQueryClient();
  const [isSaved, setIsSaved] = useState(false); // In real app, sync this with saved products list

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
      setIsSaved(!isSaved); // Optimistic UI
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-products'] });
    }
  });

  const renderStars = (rating: number) => {
    return (
      <div className="flex items-center gap-1 text-star">
        <Star size={12} fill="currentColor" />
        <span className="text-xs font-medium text-text-primary">{rating.toFixed(1)}</span>
        <span className="text-[10px] text-text-muted">({product.rating_number?.toLocaleString() || 0})</span>
      </div>
    );
  };

  const imageUrl = product.image_url ? `/api/image-proxy?url=${encodeURIComponent(product.image_url)}` : '';

  return (
    <div className="bg-bg-card rounded-2xl overflow-hidden border border-border-light hover:border-accent hover:shadow-[0_8px_30px_rgba(108,92,231,0.2)] transition-all duration-300 group cursor-pointer animate-fadeIn flex flex-col h-full">
      <div className="relative h-48 bg-white p-4 flex items-center justify-center">
        <button 
          onClick={(e) => { e.stopPropagation(); toggleSaveMutation.mutate(); }}
          className={`absolute top-2 left-2 p-2 rounded-full backdrop-blur-md transition-colors z-10
            ${isSaved ? 'bg-red-500/20 text-red-500 hover:bg-red-500/30' : 'bg-black/40 text-white hover:bg-accent'}`}
        >
          <Heart size={16} fill={isSaved ? "currentColor" : "none"} />
        </button>
        <div className="absolute top-2 right-2 bg-accent text-white text-[10px] font-bold px-2 py-1 rounded-full z-10">
          {(product.similarity_score * 100).toFixed(0)}% Match
        </div>
        
        {imageUrl ? (
          <img src={imageUrl} alt={product.title} className="max-w-full max-h-full object-contain group-hover:scale-105 transition-transform duration-300" />
        ) : (
          <div className="text-text-muted">No Image</div>
        )}
      </div>

      <div className="p-4 flex flex-col flex-1">
        <div className="text-[10px] font-bold text-accent-light uppercase tracking-wider mb-1">
          {product.main_category || 'Category'}
        </div>
        <h4 className="text-sm font-semibold text-text-primary line-clamp-2 leading-tight mb-2">
          {product.title}
        </h4>
        
        <div className="mt-auto">
          <div className="flex items-center justify-between mb-2">
            <span className="text-lg font-bold text-success">${product.price?.toFixed(2)}</span>
            {renderStars(product.average_rating || 0)}
          </div>
          
          <div className="text-xs text-text-muted mb-3 truncate">
            Sold by {product.store || 'Amazon'}
          </div>

          <div className="flex gap-2">
            <button className="flex-1 bg-bg-secondary hover:bg-sidebar-hover text-text-primary text-xs font-semibold py-2 rounded-lg transition-colors border border-border-light">
              View Details
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
