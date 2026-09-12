// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import { AvatarClient } from "./client";

describe("AvatarClient Unit Tests", () => {
  it("initializes with default options and closed/idle state", () => {
    const client = new AvatarClient({
      serverUrl: "ws://localhost:8000",
      avatarId: "female",
    });

    expect(client).toBeDefined();
    expect(client.state).toBe("idle");
    expect(client.sessionID).toBeNull();
  });

  it("registers and triggers event listeners correctly", () => {
    const client = new AvatarClient({
      serverUrl: "ws://localhost:8000",
    });

    const mockListener = vi.fn();
    client.on("speaking", mockListener);

    // Simulate internal speaking event emit
    (client as any)._emit("speaking", { speechId: "test-speech-123" });
    expect(mockListener).toHaveBeenCalledWith({ speechId: "test-speech-123" });

    // Test off
    client.off("speaking", mockListener);
    (client as any)._emit("speaking", { speechId: "test-speech-456" });
    expect(mockListener).toHaveBeenCalledTimes(1);
  });

  it("handles image source switching", () => {
    const client = new AvatarClient({
      serverUrl: "ws://localhost:8000",
    });

    expect(() => {
      client.setAvatarImage("assets/avatar_male.jpg");
    }).not.toThrow();
  });
});
