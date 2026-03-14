// filepath: frontend/tests/components/ui/badge.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/components/ui/badge";

describe("Badge", () => {
  it("renders children text", () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("applies default variant classes", () => {
    render(<Badge>Default</Badge>);
    expect(screen.getByText("Default")).toHaveClass("bg-blue-100");
  });

  it("applies success variant classes", () => {
    render(<Badge variant="success">Success</Badge>);
    expect(screen.getByText("Success")).toHaveClass("bg-emerald-100");
  });

  it("applies destructive variant classes", () => {
    render(<Badge variant="destructive">Error</Badge>);
    expect(screen.getByText("Error")).toHaveClass("bg-red-100");
  });

  it("applies warning variant classes", () => {
    render(<Badge variant="warning">Warning</Badge>);
    expect(screen.getByText("Warning")).toHaveClass("bg-yellow-100");
  });

  it("applies custom className", () => {
    render(<Badge className="extra">Test</Badge>);
    expect(screen.getByText("Test")).toHaveClass("extra");
  });
});
