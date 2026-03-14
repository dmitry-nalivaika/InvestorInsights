// filepath: frontend/src/components/layout/sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Building2,
  GitCompareArrows,
  LayoutDashboard,
  Settings,
  ClipboardList,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Companies", href: "/companies", icon: Building2 },
  { label: "Analysis Profiles", href: "/analysis/profiles", icon: ClipboardList },
  { label: "Compare", href: "/analysis/compare", icon: GitCompareArrows },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 flex-col border-r border-gray-200 bg-white">
      {/* Logo / Brand */}
      <div className="flex h-16 items-center gap-2 border-b border-gray-200 px-6">
        <BarChart3 className="h-7 w-7 text-blue-600" />
        <span className="text-lg font-bold text-gray-900">
          InvestorInsights
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900",
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-200 px-6 py-4">
        <p className="text-xs text-gray-400">InvestorInsights v1.0</p>
      </div>
    </aside>
  );
}
