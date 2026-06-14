import type { PageContextType } from '../context/PageContext';

export function buildChatContext(pageContext: PageContextType) {
  const contextPayload: any = {};
  
  if (pageContext.pageType === 'product' && pageContext.productId) {
    contextPayload.page_type = 'product';
    contextPayload.product_id = pageContext.productId;
  } else if (pageContext.pageType === 'search' && pageContext.searchQuery) {
    contextPayload.page_type = 'search';
    contextPayload.query = pageContext.searchQuery;
  } else {
    contextPayload.page_type = pageContext.pageType;
  }

  return contextPayload;
}
