// filepath: frontend/tests/components/ui/card.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  it("applies base classes", () => {
    const { container } = render(<Card>Test</Card>);
    expect(container.firstChild).toHaveClass("rounded-xl", "border", "bg-white");
  });

  it("accepts custom className", () => {
    const { container } = render(<Card className="custom">Test</Card>);
    expect(container.firstChild).toHaveClass("custom");
  });
});

describe("CardHeader", () => {
  it("renders children", () => {
    render(<CardHeader>Header</CardHeader>);
    expect(screen.getByText("Header")).toBeInTheDocument();
  });
});

describe("CardTitle", () => {
  it("renders as an h3", () => {
    render(<CardTitle>Title</CardTitle>);
    expect(screen.getByRole("heading", { level: 3, name: "Title" })).toBeInTheDocument();
  });
});

describe("CardDescription", () => {
  it("renders description text", () => {
    render(<CardDescription>Some description</CardDescription>);
    expect(screen.getByText("Some description")).toBeInTheDocument();
  });
});

describe("CardContent", () => {
  it("renders children", () => {
    render(<CardContent>Content</CardContent>);
    expect(screen.getByText("Content")).toBeInTheDocument();
  });
});

describe("CardFooter", () => {
  it("renders children", () => {
    render(<CardFooter>Footer</CardFooter>);
    expect(screen.getByText("Footer")).toBeInTheDocument();
  });
});
