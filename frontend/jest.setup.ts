import "@testing-library/jest-dom";

// jsdom does not implement EventSource — stub it so components using the
// market stream hook can mount without throwing.
class MockEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readyState = MockEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  constructor(public url: string) {}
  addEventListener(): void {}
  removeEventListener(): void {}
  close(): void {
    this.readyState = MockEventSource.CLOSED;
  }
}

Object.defineProperty(globalThis, "EventSource", {
  writable: true,
  value: MockEventSource,
});

// recharts' ResponsiveContainer needs real layout dimensions; jsdom reports 0.
Object.defineProperty(globalThis, "ResizeObserver", {
  writable: true,
  value: class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
});
