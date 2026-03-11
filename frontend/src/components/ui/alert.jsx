import * as React from "react";
import { cn } from "../../utils";
import "./css/alert.css";

const alertVariants = {
  default: "alert-default",
  destructive: "alert-destructive",
  success: "alert-success",
  warning: "alert-warning",
  info: "alert-info",
};

const Alert = React.forwardRef(({ className, variant = "default", children, ...props }, ref) => {
  return (
    <div
      ref={ref}
      role="alert"
      className={cn(
        "alert",
        alertVariants[variant],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
});

Alert.displayName = "Alert";

const AlertTitle = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <h5 ref={ref} className={cn("alert-title", className)} {...props}>
      {children}
    </h5>
  );
});

AlertTitle.displayName = "AlertTitle";

const AlertDescription = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <div ref={ref} className={cn("alert-description", className)} {...props}>
      {children}
    </div>
  );
});

AlertDescription.displayName = "AlertDescription";

export { Alert, AlertTitle, AlertDescription };