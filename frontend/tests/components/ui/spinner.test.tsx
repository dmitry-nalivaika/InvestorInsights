// filepath: frontend/tests/components/ui/spinner.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Spinner } from "@/components/ui/spinner";

describe("Spinner", () => {
  it("renders an svg element", () => {
    const { container } = render(<Spinner />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("applies animate-spin class", () => {
    const { container } = render(<Spinner />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("animate-spin");
  });

  it("accepts custom className", () => {
    const { container } = render(<Spinner className="h-8 w-8" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("h-8", "w-8");
  });
});
