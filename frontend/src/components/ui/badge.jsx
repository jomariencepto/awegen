import * as React from "react";
import { cva } from "class-variance-authority";
import { cn } from "../../utils";
import "./css/badge.css";

const badgeVariants = cva(
  "badge",
  {
    variants: {
      variant: {
        default: "badge-default",
        secondary: "badge-secondary",
        destructive: "badge-destructive",
        outline: "badge-outline",
        success: "badge-success",
        warning: "badge-warning",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

const Badge = React.forwardRef(({ className, variant, ...props }, ref) => {
  return (
    <div 
      ref={ref}
      className={cn(badgeVariants({ variant }), className)} 
      {...props} 
    />
  );
});

Badge.displayName = "Badge";

export { Badge, badgeVariants };