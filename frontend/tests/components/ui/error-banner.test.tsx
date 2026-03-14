// filepath: frontend/tests/components/ui/error-banner.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBanner } from "@/components/ui/error-banner";

describe("ErrorBanner", () => {
  it("renders the error message", () => {
    render(<ErrorBanner message="Something went wrong" />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("does not show retry button when onRetry is not provided", () => {
    render(<ErrorBanner message="Error" />);
    expect(screen.queryByText("Retry")).not.toBeInTheDocument();
  });

  it("shows retry button when onRetry is provided", () => {
    const onRetry = vi.fn();
    render(<ErrorBanner message="Error" onRetry={onRetry} />);
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("calls onRetry when retry button is clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorBanner message="Error" onRetry={onRetry} />);
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("accepts custom className", () => {
    const { container } = render(
      <ErrorBanner message="Error" className="custom-class" />,
    );
    expect(container.firstChild).toHaveClass("custom-class");
  });
});
