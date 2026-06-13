import React from 'react';
import ProductCard from './ProductCard';
import { ShoppingBag } from 'lucide-react';

interface ProductPanelProps {
  products: any[];
  isLoading: boolean;
}

export default function ProductPanel({ products, isLoading }: ProductPanelProps) {
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
          <div className="grid grid-cols-2 gap-4">
            {products.map((p, idx) => (
              <ProductCard key={`${p.parent_asin}-${idx}`} product={p} />
            ))}
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
