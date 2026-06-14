import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ProductCard from '../components/ProductCard';
import { Star, ChevronDown, Filter } from 'lucide-react';

const SearchPage = () => {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q');
  const sessionId = searchParams.get('session');
  
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchResults = async () => {
      setLoading(true);
      try {
        if (sessionId) {
          // Fetch from AI Assistant session workspace
          const res = await authFetch(`/api/chat/session/${sessionId}`);
          if (res.ok) {
            const data = await res.json();
            setProducts(data.products || []);
          }
        } else if (query) {
          // Fetch from direct search API
          const res = await authFetch(`/api/recommendations/search?q=${encodeURIComponent(query)}`);
          if (res.ok) {
            const data = await res.json();
            setProducts(data.products || []);
          }
        } else {
          setProducts([]);
        }
      } catch (err) {
        console.error("Failed to fetch search results:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [query, sessionId]);

  return (
    <div className="bg-white min-h-screen">
      {/* Top Search Info Bar */}
      <div className="border-b border-gray-200 bg-white shadow-sm px-4 py-2 text-sm flex items-center justify-between">
        <div>
          <span className="font-bold">1-{Math.max(1, products.length)} of over {products.length} results</span>
          {query && <span> for <span className="text-[#c45500] font-bold">"{query}"</span></span>}
          {sessionId && <span> for <span className="text-[#c45500] font-bold">"AI Recommendations"</span></span>}
        </div>
        <div className="flex items-center gap-2 cursor-pointer bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded-md border border-gray-300">
          <span className="text-sm">Sort by: Featured</span>
          <ChevronDown size={16} />
        </div>
      </div>

      <div className="flex max-w-[1500px] mx-auto">
        {/* Left Sidebar Filters */}
        <div className="w-[240px] hidden md:block border-r border-gray-100 p-4 shrink-0">
          <h3 className="font-bold mb-2">Departments</h3>
          <ul className="text-sm space-y-1 mb-6 text-gray-700">
            <li className="hover:text-[#c45500] cursor-pointer">Electronics</li>
            <li className="hover:text-[#c45500] cursor-pointer">Computers & Accessories</li>
            <li className="hover:text-[#c45500] cursor-pointer">Smart Home</li>
            <li className="hover:text-[#c45500] cursor-pointer">Toys & Games</li>
            <li className="hover:text-[#c45500] cursor-pointer font-bold">See All</li>
          </ul>

          <h3 className="font-bold mb-2">Customer Reviews</h3>
          <div className="flex items-center gap-1 mb-6 cursor-pointer hover:text-[#c45500]">
            <div className="flex text-yellow-500">
              <Star size={16} fill="currentColor" />
              <Star size={16} fill="currentColor" />
              <Star size={16} fill="currentColor" />
              <Star size={16} fill="currentColor" />
              <Star size={16} />
            </div>
            <span className="text-sm">& Up</span>
          </div>

          <h3 className="font-bold mb-2">Price</h3>
          <ul className="text-sm space-y-1 mb-6 text-gray-700">
            <li className="hover:text-[#c45500] cursor-pointer">Under $25</li>
            <li className="hover:text-[#c45500] cursor-pointer">$25 to $50</li>
            <li className="hover:text-[#c45500] cursor-pointer">$50 to $100</li>
            <li className="hover:text-[#c45500] cursor-pointer">$100 to $200</li>
            <li className="hover:text-[#c45500] cursor-pointer">$200 & Above</li>
          </ul>
        </div>

        {/* Main Search Results Area */}
        <div className="flex-1 p-4">
          <h2 className="text-2xl font-bold mb-4">Results</h2>
          
          {loading ? (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#ff9900]"></div>
            </div>
          ) : products.length === 0 ? (
            <div className="text-center py-12">
              <h3 className="text-xl font-bold mb-2">No results found.</h3>
              <p className="text-gray-600">Try checking your spelling or use more general terms</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {products.map((p, idx) => (
                <div key={idx} className="w-full">
                  <ProductCard product={p} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SearchPage;
