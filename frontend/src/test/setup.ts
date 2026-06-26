import '@testing-library/jest-dom'

// jsdom has no ResizeObserver; recharts' ResponsiveContainer relies on it. Provide a no-op polyfill
// so charts mount cleanly under test (charts render at 0px in jsdom — assertions target accessible
// captions/states, not SVG internals). Test-only; production runs in real browsers.
if (typeof globalThis.ResizeObserver === 'undefined') {
  class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserver as unknown as typeof globalThis.ResizeObserver
}
