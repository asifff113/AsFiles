
import { ButtonHTMLAttributes, forwardRef } from "react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "success";
  size?: "sm" | "md" | "lg";
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-full font-semibold transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:pointer-events-none",
          {
            "bg-gradient-to-r from-primary to-accent text-white hover:opacity-90 shadow-lg shadow-primary/25 hover:shadow-primary/40": variant === "primary",
            "bg-surface border border-white/10 text-white hover:bg-white/5": variant === "secondary",
            "bg-transparent text-gray-400 hover:text-white hover:bg-white/5": variant === "ghost",
            "bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20": variant === "danger",
            "bg-emerald-500 text-white hover:bg-emerald-600 shadow-lg shadow-emerald-500/25": variant === "success",
            
            "h-8 px-4 text-xs": size === "sm",
            "h-10 px-6 text-sm": size === "md",
            "h-12 px-8 text-base": size === "lg",
          },
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";

export { Button, cn };
