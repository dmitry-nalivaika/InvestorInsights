// filepath: frontend/tests/components/ui/empty-state.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState } from "@/components/ui/empty-state";

describe("EmptyState", () => {
  it("renders the title", () => {
    render(<EmptyState title="No items" />);
    expect(screen.getByText("No items")).toBeInTheDocument();
  });

  it("renders description when provided", () => {
    render(<EmptyState title="No items" description="Add some items" />);
    expect(screen.getByText("Add some items")).toBeInTheDocument();
  });

  it("does not render description when not provided", () => {
    const { container } = render(<EmptyState title="No items" />);
    const paragraphs = container.querySelectorAll("p");
    expect(paragraphs).toHaveLength(0);
  });

  it("renders icon when provided", () => {
    render(
      <EmptyState
        title="No items"
        icon={<span data-testid="test-icon">📦</span>}
      />,
    );
    expect(screen.getByTestId("test-icon")).toBeInTheDocument();
  });

  it("renders action when provided", () => {
    render(
      <EmptyState
        title="No items"
        action={<button>Add item</button>}
      />,
    );
    expect(screen.getByText("Add item")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    const { container } = render(
      <EmptyState title="No items" className="custom-class" />,
    );
    expect(container.firstChild).toHaveClass("custom-class");
  });
});
