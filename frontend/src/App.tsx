import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { CartProvider } from './context/CartContext';
import { PageContextProvider } from './context/PageContext';

// Pages & Components
import Header from './components/Header';
import Home from './pages/Home';
import SearchPage from './pages/SearchPage';
import ProductDetailPage from './pages/ProductDetailPage';
import CartPage from './pages/CartPage';
import SavedProducts from './pages/SavedProducts';
import AIAssistantDrawer from './components/AIAssistantDrawer';
import CartPopup from './components/CartPopup';

const queryClient = new QueryClient();

function AppRoutes() {
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex flex-col relative">
      <Header />
      <CartPopup />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/product/:asin" element={<ProductDetailPage />} />
          <Route path="/cart" element={<CartPage />} />
          <Route path="/saved-products" element={<SavedProducts />} />
        </Routes>
      </main>
      <AIAssistantDrawer />
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <CartProvider>
          <PageContextProvider>
            <Router>
              <AppRoutes />
            </Router>
          </PageContextProvider>
        </CartProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
