// filepath: frontend/tests/components/dashboard-page.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "@/app/dashboard/page";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}));

// Mock next/link
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// Mock api-client
const mockList = vi.fn();
vi.mock("@/lib/api-client", () => ({
  companiesApi: {
    list: (...args: unknown[]) => mockList(...args),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading spinner while fetching", () => {
    // Never resolve the promise so it stays loading
    mockList.mockReturnValue(new Promise(() => {}));
    render(<DashboardPage />, { wrapper: createWrapper() });
    // Spinner renders an SVG with animate-spin
    const svg = document.querySelector("svg.animate-spin");
    expect(svg).toBeInTheDocument();
  });

  it("renders page title", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    render(<DashboardPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument();
  });

  it("renders summary cards and company grid when data loads", async () => {
    mockList.mockResolvedValue({
      items: [
        {
          id: "1",
          ticker: "AAPL",
          name: "Apple Inc.",
          cik: null,
          sector: "Technology",
          industry: null,
          description: null,
          doc_count: 5,
          readiness_pct: 100,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
        {
          id: "2",
          ticker: "MSFT",
          name: "Microsoft Corp.",
          cik: null,
          sector: "Technology",
          industry: null,
          description: null,
          doc_count: 3,
          readiness_pct: 50,
          created_at: "2024-02-01T00:00:00Z",
          updated_at: "2024-02-01T00:00:00Z",
        },
      ],
      total: 2,
      limit: 50,
      offset: 0,
    });

    render(<DashboardPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });

    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.getByText("Microsoft Corp.")).toBeInTheDocument();

    // Summary cards
    expect(screen.getByText("Companies")).toBeInTheDocument();
    expect(screen.getByText("Total Documents")).toBeInTheDocument();
    expect(screen.getByText("Ready for Analysis")).toBeInTheDocument();
    expect(screen.getByText("Avg Readiness")).toBeInTheDocument();
  });

  it("shows empty state when no companies exist", async () => {
    mockList.mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    render(<DashboardPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("No companies yet")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Add your first company to get started with financial analysis."),
    ).toBeInTheDocument();
  });

  it("shows error banner when API call fails", async () => {
    mockList.mockRejectedValue(new Error("Network error"));

    render(<DashboardPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Failed to load companies.")).toBeInTheDocument();
    });

    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders Add Company link", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    render(<DashboardPage />, { wrapper: createWrapper() });
    const links = screen.getAllByRole("link");
    const addLink = links.find((l) => l.getAttribute("href") === "/companies");
    expect(addLink).toBeDefined();
  });
});
