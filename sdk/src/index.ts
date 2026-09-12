/**
 * @avatar-sdk/client — public entry point
 * Re-exports everything a consumer needs.
 */
export { AvatarClient } from "./client";
export { Renderer2D } from "./renderer2d";
export { AudioPlayer } from "./audio";
export { Transport } from "./transport";
export { AvatarWidget, createAvatarWidget } from "./widget";
export type { AvatarWidgetOptions } from "./widget";
export type {
  AvatarClientOptions,
  AvatarEventType,
  AvatarEventListener,
  AvatarEventMap,
  VisemeShape,
  VisemeEvent,
  ConnectionState,
} from "./types";


