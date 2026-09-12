/**
 * @avatar-sdk/client — public entry point
 * Re-exports everything a consumer needs.
 */
export { AvatarClient } from "./client";
export type {
  AvatarClientOptions,
  AvatarEventType,
  AvatarEventListener,
  AvatarEventMap,
  VisemeShape,
  VisemeEvent,
  ConnectionState,
} from "./types";
