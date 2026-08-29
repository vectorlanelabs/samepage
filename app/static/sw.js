// Same Page service worker (M5c) — the minimum for installability.
//
// Deliberately network-first with no offline caching: the app is entirely
// server-rendered and its data (live sessions, votes) must never be served
// stale from a cache. A fetch handler that just passes through to the network
// is what makes the PWA installable without risking a stale UI. If real
// offline support is ever wanted, cache only static shell assets here — never
// session/vote responses.
const VERSION = "v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
