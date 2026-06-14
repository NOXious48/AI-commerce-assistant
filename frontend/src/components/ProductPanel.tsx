import React from 'react';
import ProductCard from './ProductCard';
import { ShoppingBag } from 'lucide-react';

interface ProductPanelProps {
  products: any[];
  isLoading: boolean;
  consultationState?: any;
  filteringMetadata?: any;
  onProductClick?: (product: any) => void;
}

export default function ProductPanel({ products, isLoading, consultationState, filteringMetadata, onProductClick }: ProductPanelProps) {
  const hasState = consultationState && (consultationState.goal || consultationState.event || consultationState.budget || consultationState.preferred_brands?.length || consultationState.must_have_features?.length || consultationState.dietary_preferences?.length);

  // Group products by main_category
  const groupedProducts = products.reduce((acc, p) => {
    const cat = p.main_category || 'Other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(p);
    return acc;
  }, {} as Record<string, any[]>);

  return (
    <div className="w-[40%] min-w-[350px] bg-bg-primary flex flex-col h-full border-r border-border-light">
      <div className="p-4 bg-gradient-to-br from-bg-secondary to-bg-card border-b border-border-light flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-orange-500 flex items-center justify-center shadow-lg">
          <ShoppingBag size={20} className="text-white" />
        </div>
        <div>
          <h1 className="font-bold text-transparent bg-clip-text bg-gradient-to-r from-text-primary to-accent-light">
            AI Recommendations
          </h1>
          <p className="text-[11px] text-text-muted font-medium">Curated from 2,100+ Amazon Products</p>
        </div>
      </div>

      {hasState && (
        <div className="p-4 border-b border-border-light bg-bg-card">
          <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Consultation Profile</h3>
          <div className="flex flex-col gap-2">
            {consultationState.goal && (
              <div className="text-sm"><span className="text-text-muted">Goal:</span> <span className="font-medium">{consultationState.goal}</span></div>
            )}
            {consultationState.budget && (
              <div className="text-sm"><span className="text-text-muted">Budget:</span> <span className="font-medium text-green-400">{consultationState.budget}</span></div>
            )}
            {consultationState.event && (
              <div className="text-sm"><span className="text-text-muted">Event:</span> <span className="font-medium text-orange-400 capitalize">{consultationState.event.replace(/_/g, ' ')}</span></div>
            )}
            {consultationState.event_category && !consultationState.event && (
              <div className="text-sm"><span className="text-text-muted">Category:</span> <span className="font-medium capitalize">{consultationState.event_category.replace(/_/g, ' ')}</span></div>
            )}
            {consultationState.usage_context && (
              <div className="text-sm"><span className="text-text-muted">Context:</span> <span className="font-medium capitalize">{consultationState.usage_context}</span></div>
            )}
            {consultationState.people_count && (
              <div className="text-sm"><span className="text-text-muted">People:</span> <span className="font-medium">{consultationState.people_count}</span></div>
            )}
            <div className="flex flex-wrap gap-1 mt-1">
              {consultationState.preferred_brands?.map((b: string) => (
                <span key={b} className="px-2 py-0.5 bg-accent/20 text-accent-light rounded text-[10px] uppercase font-bold">{b}</span>
              ))}
              {consultationState.must_have_features?.map((f: string) => (
                <span key={f} className="px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-[10px] uppercase font-bold">{f}</span>
              ))}
              {consultationState.dietary_preferences?.map((d: string) => (
                <span key={d} className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-[10px] uppercase font-bold">{d}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-5 scrollbar-custom">
        {isLoading && products.length === 0 ? (
          <div className="grid grid-cols-2 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="bg-bg-card border border-border-light rounded-2xl h-72 overflow-hidden flex flex-col">
                <div className="h-40 animate-shimmer w-full"></div>
                <div className="p-4 space-y-3">
                  <div className="h-3 w-1/3 animate-shimmer rounded"></div>
                  <div className="h-4 w-full animate-shimmer rounded"></div>
                  <div className="h-4 w-2/3 animate-shimmer rounded"></div>
                </div>
              </div>
            ))}
          </div>
        ) : products.length > 0 ? (
          <div className="space-y-8">
            <div className="flex items-center justify-between mb-4">
              <div className="text-xs text-text-muted uppercase tracking-wider font-semibold">
                Showing {products.length} relevant products
              </div>
              {filteringMetadata?.retrieved_count && (
                <div className="flex items-center gap-2 text-[10px] px-2 py-1 bg-green-500/10 text-green-400 rounded-md border border-green-500/20" title={`Retrieved: ${filteringMetadata.retrieved_count}\nApproved: ${filteringMetadata.approved_count}\nRejected: ${filteringMetadata.rejected_count}`}>
                  <span>Quality Verified</span>
                  <span className="opacity-75">({filteringMetadata.approved_count}/{filteringMetadata.retrieved_count} passed)</span>
                </div>
              )}
            </div>
            {Object.entries(groupedProducts).map(([category, catProducts]) => (
              <div key={category} className="space-y-4">
                <h2 className="text-sm font-bold text-text-primary uppercase tracking-wide border-b border-border-light pb-2">
                  {category}
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  {catProducts.map((p, idx) => (
                    <div key={`${p.parent_asin}-${idx}`} onClick={() => onProductClick?.(p)}>
                      <ProductCard product={p} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : hasState ? (
          <div className="h-full flex flex-col items-center justify-center text-center opacity-80">
            <div className="w-16 h-16 mb-4 rounded-full border-4 border-accent border-t-transparent animate-spin"></div>
            <h2 className="text-lg font-semibold text-text-secondary mb-2">Consultation in progress...</h2>
            <p className="text-sm text-text-muted max-w-[250px]">
              I'm gathering information to find the perfect products for you.
            </p>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center opacity-60">
            <ShoppingBag size={48} className="mb-4 text-text-muted" />
            <h2 className="text-lg font-semibold text-text-secondary mb-2">Ask me to find products</h2>
            <p className="text-sm text-text-muted max-w-[250px]">
              Type a question in the chat and I'll find the best matches for you.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
