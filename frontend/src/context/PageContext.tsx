import React, { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

export interface PageContextType {
  pageType: 'home' | 'product' | 'cart' | 'search' | 'saved' | 'other';
  productId?: string;
  category?: string;
  searchQuery?: string;
}

interface PageContextValue {
  pageContext: PageContextType;
  setPageContext: (context: PageContextType) => void;
}

const PageContext = createContext<PageContextValue | undefined>(undefined);

export const PageContextProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [pageContext, setPageContext] = useState<PageContextType>({ pageType: 'home' });

  return (
    <PageContext.Provider value={{ pageContext, setPageContext }}>
      {children}
    </PageContext.Provider>
  );
};

export const usePageContext = () => {
  const context = useContext(PageContext);
  if (!context) {
    throw new Error('usePageContext must be used within a PageContextProvider');
  }
  return context;
};
