/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as agentRuns from "../agentRuns.js";
import type * as agentSpawns from "../agentSpawns.js";
import type * as calendar from "../calendar.js";
import type * as crons from "../crons.js";
import type * as http from "../http.js";
import type * as memories from "../memories.js";
import type * as memoryCourt from "../memoryCourt.js";
import type * as messages from "../messages.js";
import type * as pendingActions from "../pendingActions.js";
import type * as systemHealth from "../systemHealth.js";
import type * as thoughtLogs from "../thoughtLogs.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  agentRuns: typeof agentRuns;
  agentSpawns: typeof agentSpawns;
  calendar: typeof calendar;
  crons: typeof crons;
  http: typeof http;
  memories: typeof memories;
  memoryCourt: typeof memoryCourt;
  messages: typeof messages;
  pendingActions: typeof pendingActions;
  systemHealth: typeof systemHealth;
  thoughtLogs: typeof thoughtLogs;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {};
