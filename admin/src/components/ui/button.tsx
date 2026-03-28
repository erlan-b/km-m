import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius)] border leading-none font-semibold transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variant: {
        default: "bg-[var(--accent)] text-[var(--white-text-soft)] border-[var(--accent-pressed)] hover:bg-[var(--bg-muted)] hover:text-[var(--text-main)] hover:border-[var(--text-main)]",
        ghost: "bg-[var(--bg-surface)] text-[var(--text-main)] border-[var(--text-main)] hover:bg-[var(--bg-muted)]",
      },
      size: {
        default: "h-9 px-[14px] text-[14px]",
        sm: "h-8 px-3 text-[13px]",
        icon: "h-9 w-9 text-[14px]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
