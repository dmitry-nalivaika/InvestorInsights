// filepath: frontend/tests/components/layout/page-header.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageHeader } from "@/components/layout/page-header";

describe("PageHeader", () => {
  it("renders the title", () => {
    render(<PageHeader title="Dashboard" />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders description when provided", () => {
    render(<PageHeader title="Dashboard" description="Overview of your portfolio" />);
    expect(screen.getByText("Overview of your portfolio")).toBeInTheDocument();
  });

  it("does not render description when not provided", () => {
    const { container } = render(<PageHeader title="Dashboard" />);
    const paragraphs = container.querySelectorAll("p");
    expect(paragraphs).toHaveLength(0);
  });

  it("renders actions when provided", () => {
    render(
      <PageHeader
        title="Dashboard"
        actions={<button>Add</button>}
      />,
    );
    expect(screen.getByText("Add")).toBeInTheDocument();
  });

  it("renders title as an h1", () => {
    render(<PageHeader title="Companies" />);
    const heading = screen.getByRole("heading", { level: 1, name: "Companies" });
    expect(heading).toBeInTheDocument();
  });
});
