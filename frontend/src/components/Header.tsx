import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Search, ShoppingCart, Heart } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';

const Header = () => {
  const { user } = useAuth();
  const { cartItems } = useCart();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');

  const cartCount = cartItems.reduce((acc, item) => acc + item.quantity, 0);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // Navigate to the Search Page
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  return (
    <header className="bg-gray-900 text-white flex items-center p-2 h-16 sticky top-0 z-50">
      {/* Logo */}
      <Link to="/" className="flex items-center px-2 border border-transparent hover:border-white rounded mt-2">
        <img
          className="w-24 object-contain mt-2"
          src="http://pngimg.com/uploads/amazon/amazon_PNG11.png"
          alt="Amazon Logo"
        />
      </Link>

      {/* Search Bar */}
      <div className="flex flex-1 items-center rounded-md bg-white overflow-hidden mx-4">
        <form onSubmit={handleSearch} className="flex flex-1">
          <input
            className="h-10 p-2 w-full text-black outline-none border-none"
            type="text"
            placeholder="Search Amazon"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button type="submit" className="h-10 w-12 bg-yellow-500 flex items-center justify-center hover:bg-yellow-600 transition-colors">
            <Search className="text-gray-900" size={20} />
          </button>
        </form>
      </div>

      {/* Nav Options */}
      <div className="flex items-center space-x-2 text-sm">
        <div className="flex flex-col px-2 border border-transparent hover:border-white rounded cursor-pointer">
          <span className="text-gray-300 text-xs">Hello, {user ? user.name || user.email : 'Guest'}</span>
          <span className="font-bold">Account & Lists</span>
        </div>

        <Link to="/saved-products" className="flex flex-col px-2 border border-transparent hover:border-white rounded cursor-pointer">
          <span className="text-gray-300 text-xs">Returns</span>
          <span className="font-bold">& Orders</span>
        </Link>

        {/* Cart */}
        <Link to="/cart" className="flex items-center px-2 border border-transparent hover:border-white rounded cursor-pointer">
          <div className="relative flex items-center">
            <ShoppingCart size={32} />
            <span className="absolute top-0 right-0 -mt-1 -mr-1 bg-yellow-500 text-gray-900 rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold">
              {cartCount}
            </span>
          </div>
          <span className="font-bold mt-3 ml-1">Cart</span>
        </Link>
      </div>
    </header>
  );
};

export default Header;
