// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { AvatarWidget, createAvatarWidget } from "./widget";

describe("AvatarWidget Unit Tests", () => {
  it("initializes and mounts self-contained widget into DOM target", () => {
    const container = document.createElement("div");
    container.id = "test-target";
    document.body.appendChild(container);

    const widget = new AvatarWidget({
      target: container,
      avatar: "emma",
      title: "Test Assistant",
      welcomeMessage: "Hello tester",
    });

    expect(widget).toBeDefined();
    expect(container.querySelector(".avatar-widget-root")).not.toBeNull();
    expect(container.querySelector(".avatar-widget-title")?.textContent).toBe("Test Assistant");
  });

  it("createAvatarWidget factory function returns widget instance", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);

    const widget = createAvatarWidget({
      target: container,
      avatar: "david",
    });

    expect(widget).toBeInstanceOf(AvatarWidget);
  });
});
