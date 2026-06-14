import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Star, Plus, Minus, ShoppingCart, Bookmark, ShieldCheck, ThumbsUp, ThumbsDown, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';

export default function ProductDetailPage() {
  const { asin } = useParams<{ asin: string }>();
  const { authFetch } = useAuth();
  const { cartItems, addToCart, removeFromCart } = useCart();
  
  const [details, setDetails] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [mainImage, setMainImage] = useState('');
  
  const cartItem = cartItems.find(item => item.product_id === asin);
  const quantity = cartItem ? cartItem.quantity : 0;

  useEffect(() => {
    if (!asin) return;
    setIsLoading(true);
    authFetch(`/api/products/${asin}/details?session_id=generic_session`)
      .then(res => res.json())
      .then(data => {
        setDetails(data);
        if (data.metadata?.images?.length > 0) {
          setMainImage(data.metadata.images[0]);
        }
        (window as any).__PAGE_CONTEXT__ = {
          page_type: "product",
          product_id: asin,
          title: data.metadata?.title || "",
          brand: data.metadata?.brand || "",
          category: data.metadata?.main_category || ""
        };
        setIsLoading(false);
      })
      .catch(err => {
        console.error(err);
        setIsLoading(false);
      });
      
    return () => {
      (window as any).__PAGE_CONTEXT__ = undefined;
    };
  }, [asin]);

  const handleUpdateQuantity = (delta: number) => {
    if (delta > 0) {
      addToCart(asin!, 1);
    } else {
      removeFromCart(asin!, false);
    }
  };

  const handleSaveForLater = () => {
    alert('Saved for later');
  };

  const triggerRufusAction = (prompt: string) => {
    // In a real implementation, this would dispatch an event or call a context method 
    // to open the AIAssistantDrawer and prepopulate/send the prompt.
    // E.g., window.dispatchEvent(new CustomEvent('OPEN_AI_DRAWER', { detail: { prompt } }));
    alert(`Triggered AI Action: ${prompt}`);
  };

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-100">
        <div className="w-12 h-12 border-4 border-yellow-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!details) {
    return <div className="text-center text-red-500 mt-20">Failed to load product details.</div>;
  }

  return (
    <div className="bg-white min-h-screen">
      <div className="max-w-screen-2xl mx-auto p-4 md:p-8">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
          
          {/* Left Column: Images */}
          <div className="md:col-span-5 flex flex-col items-center">
            <div className="bg-white rounded-xl p-4 w-full aspect-square flex items-center justify-center border border-gray-200 mb-4 sticky top-20">
              {mainImage ? (
                <img src={`/api/image-proxy?url=${encodeURIComponent(mainImage)}`} alt="Product" className="max-w-full max-h-full object-contain mix-blend-multiply" />
              ) : (
                <div className="text-gray-400">No image</div>
              )}
            </div>
            {details.metadata?.images && details.metadata.images.length > 1 && (
              <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-custom w-full">
                {details.metadata.images.map((img: string, idx: number) => (
                  <button 
                    key={idx} 
                    onClick={() => setMainImage(img)}
                    className={`w-16 h-16 shrink-0 bg-white rounded p-1 border-2 transition-all ${mainImage === img ? 'border-yellow-500' : 'border-gray-200 opacity-60 hover:opacity-100'}`}
                  >
                    <img src={`/api/image-proxy?url=${encodeURIComponent(img)}`} className="w-full h-full object-contain mix-blend-multiply" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Middle Column: Details & AI Actions */}
          <div className="md:col-span-4 space-y-4">
            <h1 className="text-2xl font-bold text-gray-900 leading-tight">{details.metadata.title}</h1>
            <div className="text-sm text-blue-600 hover:underline cursor-pointer">
              {details.metadata.brand || 'Visit the Brand Store'}
            </div>

            <div className="flex items-center gap-2">
              <div className="flex text-yellow-500">
                {[...Array(5)].map((_, i) => (
                  <Star key={i} size={16} fill={i < Math.floor(details.reviews?.avg_rating || 0) ? "currentColor" : "none"} />
                ))}
              </div>
              <span className="text-blue-600 text-sm hover:underline cursor-pointer">
                {details.reviews?.total_reviews?.toLocaleString()} ratings
              </span>
            </div>

            <hr className="border-gray-200" />

            <div className="text-3xl font-medium text-gray-900">
              <span className="text-sm align-top">$</span>
              {Math.floor(details.metadata.price || 0)}
              <span className="text-sm align-top">
                {((details.metadata.price || 0) % 1).toFixed(2).substring(1)}
              </span>
            </div>

            {/* AI Rufus Quick Actions */}
            <div className="bg-gradient-to-r from-indigo-50 to-purple-50 p-4 rounded-lg border border-indigo-100 mt-6">
              <div className="flex items-center gap-2 mb-3 text-indigo-800">
                <Sparkles size={18} />
                <h3 className="font-bold text-sm">Ask AI Shopping Assistant</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                <button onClick={() => triggerRufusAction('Tell me about this product.')} className="bg-white border border-indigo-200 text-indigo-700 text-xs px-3 py-1.5 rounded-full hover:bg-indigo-50 transition-colors">
                  Ask AI About This Product
                </button>
                <button onClick={() => triggerRufusAction('Compare this with similar products.')} className="bg-white border border-indigo-200 text-indigo-700 text-xs px-3 py-1.5 rounded-full hover:bg-indigo-50 transition-colors">
                  Compare With Similar Products
                </button>
                <button onClick={() => triggerRufusAction('Find cheaper alternatives.')} className="bg-white border border-indigo-200 text-indigo-700 text-xs px-3 py-1.5 rounded-full hover:bg-indigo-50 transition-colors">
                  Find Cheaper Alternatives
                </button>
                <button onClick={() => triggerRufusAction('Explain the reviews of this product.')} className="bg-white border border-indigo-200 text-indigo-700 text-xs px-3 py-1.5 rounded-full hover:bg-indigo-50 transition-colors">
                  Explain Reviews
                </button>
                <button onClick={() => triggerRufusAction('Is this worth buying?')} className="bg-white border border-indigo-200 text-indigo-700 text-xs px-3 py-1.5 rounded-full hover:bg-indigo-50 transition-colors">
                  Is This Worth Buying?
                </button>
              </div>
            </div>

            {/* Description */}
            <div className="pt-4">
              <h3 className="font-bold text-gray-900 mb-2">About this item</h3>
              <ul className="list-disc pl-5 space-y-1 text-sm text-gray-800">
                {details.metadata.features?.map((f: string, idx: number) => (
                  <li key={idx}>{f}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Right Column: Checkout Card */}
          <div className="md:col-span-3">
            <div className="border border-gray-200 rounded-lg p-4 sticky top-20">
              <div className="text-2xl font-medium text-gray-900 mb-4">
                <span className="text-sm align-top">$</span>
                {details.metadata.price?.toFixed(2)}
              </div>
              <div className="text-green-600 font-bold mb-4">In Stock.</div>
              
              <div className="space-y-3">
                {quantity > 0 ? (
                  <div className="flex items-center justify-between border border-gray-300 rounded-full px-4 py-2">
                    <button onClick={() => handleUpdateQuantity(-1)} className="text-gray-600 hover:text-black"><Minus size={18}/></button>
                    <span className="font-bold">{quantity}</span>
                    <button onClick={() => handleUpdateQuantity(1)} className="text-gray-600 hover:text-black"><Plus size={18}/></button>
                  </div>
                ) : (
                  <button onClick={() => handleUpdateQuantity(1)} className="w-full bg-yellow-400 hover:bg-yellow-500 text-black py-2 rounded-full font-medium shadow-sm transition-colors">
                    Add to Cart
                  </button>
                )}
                
                <button className="w-full bg-orange-400 hover:bg-orange-500 text-black py-2 rounded-full font-medium shadow-sm transition-colors">
                  Buy Now
                </button>
              </div>

              <div className="mt-4 pt-4 border-t border-gray-200 flex justify-center">
                <button onClick={handleSaveForLater} className="text-sm text-blue-600 hover:underline flex items-center gap-1">
                  <Bookmark size={14} /> Add to List
                </button>
              </div>
            </div>
          </div>

        </div>

        {/* Similar Products Shelf */}
        <div className="mt-16 border-t border-gray-200 pt-8">
          <h2 className="text-xl font-bold mb-4 text-gray-900">Similar Products</h2>
          <SimilarProductsShelf asin={asin || ''} authFetch={authFetch} />
        </div>

      </div>
    </div>
  );
}

function SimilarProductsShelf({ asin, authFetch }: { asin: string, authFetch: any }) {
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!asin) return;
    const fetchSimilar = async () => {
      try {
        const res = await authFetch(`/api/recommendations/similar/${asin}`);
        if (res.ok) {
          const data = await res.json();
          setProducts(data.similar_products || []);
        }
        setLoading(false);
      } catch (e) {
        console.error(e);
        setLoading(false);
      }
    };
    fetchSimilar();
  }, [asin, authFetch]);

  if (loading) return <div className="text-gray-500">Loading similar products...</div>;
  if (products.length === 0) return <div className="text-gray-500">No similar products found.</div>;

  return (
    <div className="flex space-x-4 overflow-x-auto pb-4 scrollbar-custom">
      {products.map((p, idx) => (
        <div key={idx} className="w-[200px] shrink-0">
          <a href={`/product/${p.parent_asin}`} className="block border border-gray-200 rounded-lg p-2 hover:shadow-md transition-shadow bg-white h-full">
            <div className="w-full h-32 flex items-center justify-center mb-2">
              {p.images && p.images.length > 0 ? (
                <img src={`/api/image-proxy?url=${encodeURIComponent(p.images[0])}`} className="max-h-full object-contain mix-blend-multiply" />
              ) : (
                <div className="text-gray-400 text-xs">No image</div>
              )}
            </div>
            <div className="text-xs font-medium text-gray-900 line-clamp-2 mb-1">{p.title}</div>
            <div className="text-sm font-bold text-gray-900">${p.price?.toFixed(2) || '0.00'}</div>
          </a>
        </div>
      ))}
    </div>
  );
}
