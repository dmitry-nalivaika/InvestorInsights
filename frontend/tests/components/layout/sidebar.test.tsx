// filepath: frontend/tests/components/layout/sidebar.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "@/components/layout/sidebar";

// Mock next/navigation
const mockUsePathname = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

// Mock next/link to render a plain <a>
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("Sidebar", () => {
  beforeEach(() => {
    mockUsePathname.mockReturnValue("/dashboard");
  });

  it("renders the brand name", () => {
    render(<Sidebar />);
    expect(screen.getByText("InvestorInsights")).toBeInTheDocument();
  });

  it("renders all navigation items", () => {
    render(<Sidebar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Companies")).toBeInTheDocument();
    expect(screen.getByText("Analysis Profiles")).toBeInTheDocument();
    expect(screen.getByText("Compare")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders navigation links with correct hrefs", () => {
    render(<Sidebar />);
    expect(screen.getByText("Dashboard").closest("a")).toHaveAttribute("href", "/dashboard");
    expect(screen.getByText("Companies").closest("a")).toHaveAttribute("href", "/companies");
    expect(screen.getByText("Settings").closest("a")).toHaveAttribute("href", "/settings");
  });

  it("highlights the active nav item", () => {
    mockUsePathname.mockReturnValue("/settings");
    render(<Sidebar />);
    const settingsLink = screen.getByText("Settings").closest("a");
    expect(settingsLink).toHaveClass("bg-blue-50", "text-blue-700");
  });

  it("does not highlight inactive nav items", () => {
    mockUsePathname.mockReturnValue("/dashboard");
    render(<Sidebar />);
    const settingsLink = screen.getByText("Settings").closest("a");
    expect(settingsLink).not.toHaveClass("bg-blue-50");
  });

  it("renders the version footer", () => {
    render(<Sidebar />);
    expect(screen.getByText("InvestorInsights v1.0")).toBeInTheDocument();
  });
});
