/* Obsidian Sentinel / adapter boundary between UI components and demo data. */

import { getHedgeRun, RUN_STATE_INDEX } from "@/demo/mockData";
import type { HedgeRun, RunState } from "@/demo/models";

export interface DemoApi {
  getRun(state: RunState): Promise<HedgeRun>;
  getStateIndex(state: RunState): number;
}

/**
 * Replace this adapter with a REST/SSE implementation when a live runner is available.
 * Components intentionally depend on this narrow contract only.
 */
export const demoApi: DemoApi = {
  async getRun(state) {
    return getHedgeRun(state);
  },
  getStateIndex(state) {
    return RUN_STATE_INDEX[state];
  },
};
