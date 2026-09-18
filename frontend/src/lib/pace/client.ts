/**
 * The PaceClient boundary.
 *
 * The prototype resolves to MockPaceClient. The intended production adapter is
 * an HttpPaceClient that calls the local Python API on the same origin at
 * /api/v1/*. That adapter is deliberately NOT implemented yet: this prototype
 * makes no network requests at all.
 *
 * Future shape, for reference only:
 *
 *   class HttpPaceClient implements PaceClient {
 *     getToday() { return this.get<TodayView>("/api/v1/today"); }
 *     sendCoachMessage(text) { return this.post("/api/v1/coach/messages", { text }); }
 *     ...
 *   }
 *
 * Swapping adapters must not require any component change.
 */

import { HttpPaceClient } from "./http-client";
import { MockPaceClient } from "./mock-client";
import type { PaceClient } from "./types";

let instance: PaceClient | null = null;

export function getPaceClient(): PaceClient {
  if (!instance) {
    instance =
      import.meta.env.VITE_PACE_USE_MOCKS === "true" ? new MockPaceClient() : new HttpPaceClient();
  }
  return instance;
}

/** True while the UI runs on synthetic data. Drives the "synthetic demo" marks. */
export const IS_PROTOTYPE_DATA = import.meta.env.VITE_PACE_USE_MOCKS === "true";

export type { PaceClient };
