import * as React from "react";

import { cn } from "@/shared/lib";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          // min-h-11 guarantees a 44px touch target on mobile (PRD §7 a11y).
          "inline-flex min-h-11 items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50",
          variant === "default" && "bg-slate-900 text-slate-50 hover:bg-slate-800",
          variant === "outline" && "border border-slate-300 bg-transparent hover:bg-slate-100",
          className,
        )}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
