// filepath: frontend/src/components/ui/badge.tsx
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { type HTMLAttributes } from "react";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-blue-100 text-blue-800",
        success: "bg-emerald-100 text-emerald-800",
        warning: "bg-yellow-100 text-yellow-800",
        destructive: "bg-red-100 text-red-800",
        secondary: "bg-gray-100 text-gray-800",
        outline: "border border-gray-300 text-gray-700",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}
