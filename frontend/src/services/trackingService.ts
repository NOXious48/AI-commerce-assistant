// trackingService.ts
// Handles batched click tracking, deduplication, and retry queue

interface TrackingEvent {
  event_type: 'Viewed' | 'Clicked' | 'Compared' | 'Added To Cart' | 'Saved';
  product_id: string;
  timestamp: string;
  session_id?: string;
  domain?: string;
}

class TrackingService {
  private queue: TrackingEvent[] = [];
  private retryQueue: { event: TrackingEvent; retries: number }[] = [];
  private dedupeCache: Map<string, number> = new Map();
  private flushInterval: any;
  private readonly MAX_RETRIES = 3;
  private readonly DEDUPE_TTL = 10 * 60 * 1000; // 10 minutes

  constructor() {
    this.startInterval();
    this.setupWindowListeners();
  }

  private startInterval() {
    if (typeof window !== 'undefined') {
      this.flushInterval = setInterval(() => this.flush(), 30000); // 30 seconds
    }
  }

  private setupWindowListeners() {
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => this.flushSync());
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
          this.flush();
        }
      });
    }
  }

  public track(event: TrackingEvent) {
    const dedupeKey = `${event.event_type}_${event.product_id}`;
    const now = Date.now();

    // Deduplication check
    if (this.dedupeCache.has(dedupeKey)) {
      const lastTime = this.dedupeCache.get(dedupeKey)!;
      if (now - lastTime < this.DEDUPE_TTL) {
        return; // Skip duplicate event
      }
    }

    this.dedupeCache.set(dedupeKey, now);
    this.queue.push(event);

    if (this.queue.length >= 10) {
      this.flush();
    }
  }

  private async flush() {
    if (this.queue.length === 0 && this.retryQueue.length === 0) return;

    const eventsToSend = [...this.queue];
    this.queue = [];

    // Add retry events
    const retryEvents = this.retryQueue.map(item => item.event);
    const allEvents = [...eventsToSend, ...retryEvents];

    if (allEvents.length === 0) return;

    try {
      // Get token from localStorage (simplified for tracking service)
      const token = localStorage.getItem('access_token');
      if (!token) return; // Drop events if not logged in

      const res = await fetch('/api/tracking/batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ events: allEvents }),
      });

      if (!res.ok) throw new Error('Tracking flush failed');

      // Success: clear retry queue
      this.retryQueue = [];
      
    } catch (error) {
      console.warn('Tracking flush failed, adding to retry queue');
      
      // Re-queue failed new events
      eventsToSend.forEach(e => this.retryQueue.push({ event: e, retries: 1 }));
      
      // Increment retries for existing retry events and drop if max exceeded
      this.retryQueue = this.retryQueue
        .map(item => ({ ...item, retries: item.retries + 1 }))
        .filter(item => item.retries <= this.MAX_RETRIES);
    }
  }

  private flushSync() {
    // Synchronous flush for beforeunload using keepalive
    if (this.queue.length === 0) return;
    
    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
      fetch('/api/tracking/batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ events: this.queue }),
        keepalive: true // Crucial for unload
      });
      this.queue = [];
    } catch (e) {
      console.error('Sync flush failed', e);
    }
  }
}

export const trackingService = new TrackingService();
