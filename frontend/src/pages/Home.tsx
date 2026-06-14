import React, { useState, useEffect } from 'react';
import ProductCard from '../components/ProductCard';
import CategoryCard from '../components/CategoryCard';
import { useAuth } from '../context/AuthContext';

import RecommendationShelf from '../components/RecommendationShelf';

const Home = () => {
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const { authFetch } = useAuth();
  
  const [activeDomains, setActiveDomains] = useState<string[]>(() => {
    try {
        const stored = localStorage.getItem('ai_active_domains');
        return stored ? JSON.parse(stored).filter((d: string) => d !== 'general' && d !== 'general_shopping') : [];
    } catch { return []; }
  });
  const [sessionId, setSessionId] = useState<string | null>(() => {
    return localStorage.getItem('ai_session_id');
  });

  useEffect(() => {
    const handleStateUpdate = (e: any) => {
        if (e.detail && e.detail.sessionId) {
            setSessionId(e.detail.sessionId);
        }
        if (e.detail && e.detail.state && e.detail.state.active_domains) {
            // Filter out generic domains since we want specific shelves
            const filtered = e.detail.state.active_domains.filter((d: string) => d !== 'general' && d !== 'general_shopping');
            setActiveDomains(filtered);
            localStorage.setItem('ai_active_domains', JSON.stringify(e.detail.state.active_domains));
            localStorage.setItem('ai_session_id', e.detail.sessionId);
        }
    };
    window.addEventListener('ai-state-updated', handleStateUpdate);
    return () => window.removeEventListener('ai-state-updated', handleStateUpdate);
  }, []);

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const res = await authFetch('/api/recommendations/home');
        if (res.ok) {
          const data = await res.json();
          setProducts(data.recommendations || []);
        }
        setLoading(false);
      } catch (e) {
        console.error(e);
        setLoading(false);
      }
    };
    fetchProducts();
  }, [authFetch]);

  // Mock data for Amazon-style category cards
  const categoryCards = [
    {
      title: "Appliances for your home | Up to 55% off",
      items: [
        { title: "Air conditioners", image: "https://m.media-amazon.com/images/I/51m9CcqebHL._AC_.jpg", link: "/search?q=air+conditioner" },
        { title: "Refrigerators", image: "https://m.media-amazon.com/images/I/41tgcIqS7eL.jpg", link: "/search?q=refrigerator" },
        { title: "Microwaves", image: "https://m.media-amazon.com/images/I/51UPP+wmzGL.jpg", link: "/search?q=microwave" },
        { title: "Washing machines", image: "https://m.media-amazon.com/images/I/51GICyCujFL._AC_.jpg", link: "/search?q=washing+machine" },
      ],
      footerText: "See more"
    },
    {
      title: "Revamp your home in style",
      items: [
        { title: "Cushion covers", image: "https://m.media-amazon.com/images/I/41PMSKa8xrL._AC_.jpg", link: "/search?q=cushion" },
        { title: "Figurines, vases", image: "https://m.media-amazon.com/images/I/51T7yzLPHTL.jpg", link: "/search?q=figurine" },
        { title: "Home storage", image: "https://m.media-amazon.com/images/I/41u1+S-9vAL.jpg", link: "/search?q=storage" },
        { title: "Lighting solutions", image: "https://m.media-amazon.com/images/I/51+vN2pUo5L.jpg", link: "/search?q=lighting" },
      ],
      footerText: "Explore all"
    },
    {
      title: "Starting ₹49 | Deals on home essentials",
      items: [
        { title: "Cleaning supplies", image: "https://m.media-amazon.com/images/I/31MDn4yjr8L._AC_.jpg", link: "/search?q=cleaning" },
        { title: "Bathroom accessories", image: "https://m.media-amazon.com/images/I/31l2EKufKML._AC_.jpg", link: "/search?q=bathroom" },
        { title: "Tools", image: "https://m.media-amazon.com/images/I/41jfopK8YjL.jpg", link: "/search?q=tools" },
        { title: "Wallpapers", image: "https://m.media-amazon.com/images/I/51MeBqlCILL.jpg", link: "/search?q=wallpaper" },
      ],
      footerText: "Shop now"
    },
    {
      title: "Up to 50% off | Baby care & toys",
      items: [
        { title: "Baby diapers", image: "https://m.media-amazon.com/images/I/512NWPqTKwL._AC_.jpg", link: "/search?q=diaper" },
        { title: "Ride ons", image: "https://m.media-amazon.com/images/I/41YNx3Y-X2S._AC_.jpg", link: "/search?q=ride+on" },
        { title: "RC cars", image: "https://m.media-amazon.com/images/I/51PR4gzsO-L.jpg", link: "/search?q=rc+car" },
        { title: "Baby safety", image: "https://m.media-amazon.com/images/I/31F7zrxmoDL._AC_.jpg", link: "/search?q=baby+safety" },
      ],
      footerText: "See more"
    }
  ];

  return (
    <div className="bg-[#E3E6E6] min-h-screen">
      {/* Hero Image */}
      <div className="relative">
        <img
          className="w-full object-cover h-[350px] md:h-[450px]"
          style={{ maskImage: 'linear-gradient(to bottom, rgba(0,0,0,1) 40%, rgba(0,0,0,0) 100%)' }}
          src="https://images-eu.ssl-images-amazon.com/images/G/02/digital/video/merch2016/Hero/Covid19/Generic/GWBleedingHero_ENG_COVIDUPDATE__XSite_1500x600_PV_en-GB._CB428684220_.jpg"
          alt="Hero Banner"
        />
      </div>

      <div className="max-w-screen-2xl mx-auto px-4 -mt-32 md:-mt-64 relative z-10 space-y-6 pb-8">
        
        {/* Top Categories Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {categoryCards.map((card, idx) => (
            <CategoryCard key={idx} {...card} />
          ))}
        </div>

        {/* Dynamic AI Session Shelves */}
        {activeDomains.length > 0 && sessionId && (
            <div className="bg-white p-4 shadow-sm mb-6 rounded-lg">
                <div className="flex items-center space-x-2 mb-2">
                   <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                   <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Live AI Session</h2>
                </div>
                {activeDomains.map(domain => (
                    <RecommendationShelf key={domain} domain={domain} sessionId={sessionId} />
                ))}
            </div>
        )}

        {/* Recommended For You Shelf */}
        <div className="bg-white p-4 flex flex-col shadow-sm">
          <h2 className="text-xl font-bold mb-4 text-gray-900">Recommended For You</h2>
          {loading ? (
             <div className="text-gray-500">Loading recommendations...</div>
          ) : (
            <div className="flex space-x-4 overflow-x-auto pb-4 scrollbar-custom">
              {products.length > 0 ? (
                products.map((p, idx) => (
                  <div key={idx} className="w-[200px] shrink-0">
                    <ProductCard product={p} />
                  </div>
                ))
              ) : (
                <div className="text-gray-500">No recommendations found.</div>
              )}
            </div>
          )}
        </div>

        {/* Product Grid */}
        <div className="bg-white p-4 shadow-sm">
          <h2 className="text-xl font-bold mb-4 text-gray-900">More Top Products</h2>
          {loading ? (
            <div>Loading products...</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {products.slice(0, 12).map((p, idx) => (
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

export default Home;
