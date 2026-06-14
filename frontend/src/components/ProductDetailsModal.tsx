import React, { useState, useEffect } from 'react';
import { X, Star, Plus, Minus, ShoppingCart, Bookmark, ShieldCheck, ThumbsUp, ThumbsDown, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface ProductDetailsModalProps {
  sessionId: string | null;
  product: any;
  onClose: () => void;
  cartItems: any[];
  setCartItems: (items: any[]) => void;
}

export default function ProductDetailsModal({ sessionId, product, onClose, cartItems, setCartItems }: ProductDetailsModalProps) {
  const { authFetch } = useAuth();
  const [details, setDetails] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [mainImage, setMainImage] = useState(product.image_url);

  const cartItem = cartItems.find(i => i.product_id === product.parent_asin);
  const quantity = cartItem ? cartItem.quantity : 0;

  useEffect(() => {
    if (!product || !sessionId) return;
    setIsLoading(true);
    authFetch(`/api/products/${product.parent_asin}/details?session_id=${sessionId}`)
      .then(res => res.json())
      .then(data => {
        setDetails(data);
        if (data.metadata?.images?.length > 0) {
          setMainImage(data.metadata.images[0]);
        }
        setIsLoading(false);
      })
      .catch(err => {
        console.error(err);
        setIsLoading(false);
      });
  }, [product, sessionId]);

  const handleUpdateQuantity = async (delta: number) => {
    if (!sessionId) return;
    const newQty = quantity + delta;
    
    try {
      if (newQty <= 0) {
        await authFetch('/api/cart/remove', {
          method: 'POST',
          body: JSON.stringify({ session_id: sessionId, product_id: product.parent_asin, fully_remove: true })
        });
        setCartItems(cartItems.filter(i => i.product_id !== product.parent_asin));
      } else if (delta > 0) {
        await authFetch('/api/cart/add', {
          method: 'POST',
          body: JSON.stringify({ session_id: sessionId, product_id: product.parent_asin, quantity: delta })
        });
        if (quantity === 0) {
          // If first time adding, we might not have all metadata perfectly synced immediately from backend, but optimistically add
          setCartItems([...cartItems, {
            product_id: product.parent_asin,
            title: details?.metadata?.title || product.title,
            price: details?.metadata?.price || product.price,
            quantity: 1,
            image: mainImage
          }]);
        } else {
          setCartItems(cartItems.map(i => i.product_id === product.parent_asin ? { ...i, quantity: newQty } : i));
        }
      } else {
        await authFetch('/api/cart/remove', {
          method: 'POST',
          body: JSON.stringify({ session_id: sessionId, product_id: product.parent_asin, fully_remove: false })
        });
        setCartItems(cartItems.map(i => i.product_id === product.parent_asin ? { ...i, quantity: newQty } : i));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSaveForLater = () => {
    // Implement save for later if API exists
    alert('Saved for later (Feature in development)');
  };

  if (!product) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-bg-primary w-full max-w-4xl h-[85vh] rounded-2xl shadow-2xl flex flex-col border border-border-light overflow-hidden animate-fadeIn">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border-light bg-bg-card">
          <h2 className="font-bold text-text-primary text-lg truncate pr-4">Product Details</h2>
          <button onClick={onClose} className="p-2 hover:bg-bg-secondary rounded-full transition-colors text-text-muted hover:text-white">
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-custom">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-full opacity-60">
              <div className="w-12 h-12 mb-4 border-4 border-accent border-t-transparent rounded-full animate-spin"></div>
              <p className="text-text-muted">Loading product insights...</p>
            </div>
          ) : details ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              
              {/* Left Column: Images & Meta */}
              <div className="space-y-6">
                <div className="bg-white rounded-xl p-4 aspect-square flex items-center justify-center border border-border-light">
                  <img src={mainImage} alt="Product" className="max-w-full max-h-full object-contain mix-blend-multiply" />
                </div>
                {details.metadata?.images && details.metadata.images.length > 1 && (
                  <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-custom">
                    {details.metadata.images.map((img: string, idx: number) => (
                      <button 
                        key={idx} 
                        onClick={() => setMainImage(img)}
                        className={`w-16 h-16 shrink-0 bg-white rounded-lg p-1 border-2 transition-all ${mainImage === img ? 'border-accent' : 'border-border-light opacity-60 hover:opacity-100'}`}
                      >
                        <img src={img} className="w-full h-full object-contain mix-blend-multiply" />
                      </button>
                    ))}
                  </div>
                )}

                <div>
                  <h1 className="text-xl font-bold text-text-primary mb-2 leading-tight">{details.metadata.title}</h1>
                  <div className="flex items-center gap-4 text-sm text-text-muted mb-4">
                    <span className="bg-bg-secondary px-2 py-1 rounded text-accent-light font-bold">{details.metadata.brand}</span>
                    <span>{details.metadata.category}</span>
                  </div>
                  <div className="text-3xl font-bold text-green-400 mb-6">${details.metadata.price}</div>
                </div>

                {/* Description */}
                {details.metadata.description && (
                  <div className="bg-bg-secondary/50 p-4 rounded-xl border border-border-light">
                    <h3 className="text-sm font-bold text-text-secondary uppercase mb-2">Description</h3>
                    <p className="text-sm text-text-muted line-clamp-4 hover:line-clamp-none transition-all">{details.metadata.description}</p>
                  </div>
                )}
              </div>

              {/* Right Column: AI Insights & Reviews */}
              <div className="space-y-6">
                
                {/* AI Summary */}
                <div className="bg-gradient-to-br from-accent/10 to-orange-500/10 p-5 rounded-xl border border-accent/20">
                  <div className="flex items-center gap-2 mb-2 text-accent-light">
                    <Sparkles size={18} />
                    <h3 className="font-bold">AI Summary</h3>
                  </div>
                  <p className="text-sm text-text-primary leading-relaxed">
                    {details.recommendation.ai_summary}
                  </p>
                </div>

                {/* Why Recommended */}
                {(details.recommendation.approval_reasons?.length > 0 || details.recommendation.rejected_reasons?.length > 0) && (
                  <div className="bg-bg-card p-5 rounded-xl border border-border-light">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-bold text-text-secondary flex items-center gap-2">
                        <ShieldCheck size={18} className="text-green-400" />
                        {details.recommendation.alignment_score ? 'Why Recommended' : 'Filtering Status'}
                      </h3>
                      {details.recommendation.alignment_score && (
                        <div className="text-xs font-bold bg-green-500/20 text-green-400 px-2 py-1 rounded">
                          Score: {details.recommendation.alignment_score}/100
                        </div>
                      )}
                    </div>
                    <ul className="space-y-2">
                      {details.recommendation.approval_reasons?.map((reason: string, idx: number) => (
                        <li key={idx} className="flex gap-2 text-sm text-text-primary">
                          <span className="text-green-400 shrink-0">✓</span> {reason}
                        </li>
                      ))}
                      {details.recommendation.rejected_reasons?.map((reason: string, idx: number) => (
                        <li key={idx} className="flex gap-2 text-sm text-text-primary opacity-60">
                          <span className="text-red-400 shrink-0">✗</span> {reason}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Review Highlights */}
                <div className="bg-bg-card p-5 rounded-xl border border-border-light">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="flex items-center text-yellow-400 font-bold text-lg gap-1">
                      <Star size={20} fill="currentColor" />
                      {details.reviews.avg_rating}
                    </div>
                    <div className="text-text-muted text-sm border-l border-border-light pl-3">
                      Based on {details.reviews.total_reviews} reviews
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="bg-green-500/10 p-3 rounded-lg border border-green-500/20">
                      <div className="flex items-center gap-1 text-green-400 font-bold mb-2 text-sm"><ThumbsUp size={14}/> Top Praises</div>
                      <ul className="text-xs text-text-muted space-y-1">
                        {details.reviews.positive_highlights.slice(0,3).map((h:string, i:number) => <li key={i} className="capitalize flex gap-1"><span>•</span>{h}</li>)}
                        {details.reviews.positive_highlights.length === 0 && <li>No specific praises extracted</li>}
                      </ul>
                    </div>
                    <div className="bg-red-500/10 p-3 rounded-lg border border-red-500/20">
                      <div className="flex items-center gap-1 text-red-400 font-bold mb-2 text-sm"><ThumbsDown size={14}/> Top Complaints</div>
                      <ul className="text-xs text-text-muted space-y-1">
                        {details.reviews.negative_highlights.slice(0,3).map((h:string, i:number) => <li key={i} className="capitalize flex gap-1"><span>•</span>{h}</li>)}
                        {details.reviews.negative_highlights.length === 0 && <li>No specific complaints extracted</li>}
                      </ul>
                    </div>
                  </div>
                </div>

                {/* Features */}
                {details.metadata.features?.length > 0 && (
                  <div className="bg-bg-card p-5 rounded-xl border border-border-light">
                    <h3 className="font-bold text-text-secondary mb-3">Key Features</h3>
                    <ul className="space-y-2">
                      {details.metadata.features.map((f: string, idx: number) => (
                        <li key={idx} className="flex gap-2 text-sm text-text-muted">
                          <span className="text-accent shrink-0">•</span> {f}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center text-red-400 mt-20">Failed to load details.</div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-border-light bg-bg-secondary flex justify-end gap-3 shrink-0">
          <button onClick={handleSaveForLater} className="px-6 py-2.5 flex items-center gap-2 rounded-xl border border-border-light text-text-muted hover:text-white hover:bg-bg-card transition-colors font-semibold">
            <Bookmark size={18} /> Save for Later
          </button>
          
          {quantity > 0 ? (
            <div className="flex items-center gap-4 bg-gradient-to-r from-accent to-orange-500 p-1 rounded-xl shadow-lg">
              <button onClick={() => handleUpdateQuantity(-1)} className="p-2 text-white hover:bg-white/20 rounded-lg transition-colors"><Minus size={18}/></button>
              <span className="text-white font-bold min-w-[20px] text-center">{quantity}</span>
              <button onClick={() => handleUpdateQuantity(1)} className="p-2 text-white hover:bg-white/20 rounded-lg transition-colors"><Plus size={18}/></button>
            </div>
          ) : (
            <button onClick={() => handleUpdateQuantity(1)} className="px-8 py-2.5 flex items-center gap-2 bg-gradient-to-r from-accent to-orange-500 hover:from-accent-light hover:to-orange-400 text-white font-bold rounded-xl shadow-lg shadow-accent/20 transition-all">
              <ShoppingCart size={18} /> Add To Cart
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
