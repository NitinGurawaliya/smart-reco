import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "synced" | "failed" | "pending" | "outline";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variant === "default" && "bg-[#e6f4f4] text-[#0a6e70]",
        variant === "synced" && "bg-green-100 text-green-700",
        variant === "failed" && "bg-red-100 text-red-700",
        variant === "pending" && "bg-amber-100 text-amber-700",
        variant === "outline" && "border border-[#D1CAB8] text-[#6B7280] bg-transparent",
        className
      )}
      {...props}
    />
  );
}
