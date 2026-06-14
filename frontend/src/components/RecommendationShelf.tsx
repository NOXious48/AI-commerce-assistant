import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import ProductCard from './ProductCard';
import { Sparkles, Info } from 'lucide-react';

interface RecommendationShelfProps {
  domain: string;
  sessionId: string;
  title?: string;
}

export default function RecommendationShelf({ domain, sessionId, title }: RecommendationShelfProps) {
  const { authFetch } = useAuth();

  const { data, isLoading, error } = useQuery({
    queryKey: ['shelf', domain, sessionId],
    queryFn: async () => {
      const res = await authFetch(`/api/recommendations/shelf?domain=${domain}&session_id=${sessionId}`);
      if (!res.ok) throw new Error('Failed to fetch shelf');
      return res.json();
    },
    enabled: !!domain && !!sessionId
  });

  if (isLoading) {
    return (
      <div className="py-8 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-48 mb-6"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {[1,2,3,4,5].map(i => <div key={i} className="h-64 bg-gray-100 rounded"></div>)}
        </div>
      </div>
    );
  }

  if (error || !data) return null;

  if (data.shelf_type === 'empty' || !data.products || data.products.length === 0) {
    return (
      <div className="py-8 border border-dashed border-gray-300 rounded-lg bg-gray-50 flex flex-col items-center justify-center text-center p-6 my-4">
        <Sparkles size={32} className="text-gray-400 mb-3" />
        <h3 className="text-lg font-medium text-gray-700">No recommendations yet</h3>
        <p className="text-sm text-gray-500 mt-1 max-w-md">
          Start a shopping conversation with Rufus, our AI assistant, to receive curated recommendations tailored to your specific needs.
        </p>
        <button 
          onClick={() => window.dispatchEvent(new CustomEvent('open-ai-drawer', { detail: { prompt: `Help me shop for ${domain.replace('_', ' ')}` } }))}
          className="mt-4 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-medium py-2 px-4 rounded-full text-sm transition-colors"
        >
          Ask AI Assistant
        </button>
      </div>
    );
  }

  const basedOnText = Object.entries(data.based_on || {}).map(([k, v]) => {
    if (Array.isArray(v)) return `${k}: ${v.join(', ')}`;
    return `${k}: ${v}`;
  }).join(' | ');

  return (
    <div className="py-8 border-t border-gray-100">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-2">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Sparkles size={20} className="text-purple-500" />
            {title || `Recommended for ${domain.replace('_', ' ')}`}
          </h2>
          {basedOnText && (
            <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
              <Info size={12} /> Based on: {basedOnText}
            </p>
          )}
        </div>
        <div className="text-[10px] text-gray-400 font-mono text-right hidden md:block">
          <div>Version {data.recommendation_version}</div>
          <div>{new Date(data.generated_at).toLocaleString()}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
        {data.products.map((product: any) => (
          <ProductCard 
            key={product.parent_asin} 
            product={product} 
            sessionId={sessionId}
            domain={domain}
            planId={data.recommendation_version?.toString()}
          />
        ))}
      </div>
    </div>
  );
}
