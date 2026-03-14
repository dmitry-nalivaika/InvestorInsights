// filepath: frontend/tests/components/ui/button.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });

  it("renders as a button element", () => {
    render(<Button>Test</Button>);
    expect(screen.getByRole("button", { name: "Test" })).toBeInTheDocument();
  });

  it("handles click events", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    fireEvent.click(screen.getByText("Click"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("can be disabled", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("applies variant classes", () => {
    render(<Button variant="destructive">Delete</Button>);
    const btn = screen.getByRole("button");
    expect(btn).toHaveClass("bg-red-600");
  });

  it("applies size classes", () => {
    render(<Button size="sm">Small</Button>);
    const btn = screen.getByRole("button");
    expect(btn).toHaveClass("h-8");
  });

  it("applies custom className", () => {
    render(<Button className="extra-class">Test</Button>);
    expect(screen.getByRole("button")).toHaveClass("extra-class");
  });
});
