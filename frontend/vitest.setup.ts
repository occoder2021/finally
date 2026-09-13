import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver; Recharts' ResponsiveContainer needs one.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (ResizeObserverStub as unknown as typeof ResizeObserver);

// jsdom has no EventSource; this harmless default avoids "EventSource is not
// defined" for any component that constructs one during a test. Suites that
// care about stream behavior mock hooks/usePriceStream.ts directly instead.
class EventSourceStub {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readyState = EventSourceStub.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  close() {
    this.readyState = EventSourceStub.CLOSED;
  }
  addEventListener() {}
  removeEventListener() {}
}
globalThis.EventSource = globalThis.EventSource ?? (EventSourceStub as unknown as typeof EventSource);

// Element.animate isn't implemented in jsdom; used for the price-flash fade.
if (!Element.prototype.animate) {
  // @ts-expect-error -- test polyfill
  Element.prototype.animate = () => ({
    onfinish: null,
    cancel: () => {},
    finish: () => {},
  });
}

// jsdom doesn't implement scrollTo; ChatPanel calls it to auto-scroll to the
// latest message.
if (!Element.prototype.scrollTo) {
  // @ts-expect-error -- test polyfill
  Element.prototype.scrollTo = () => {};
}
