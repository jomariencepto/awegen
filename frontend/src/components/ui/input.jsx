import * as React from "react";
import { cn } from "../../utils";
import "./css/input.css";

const Input = React.forwardRef(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn("input", className)}
    {...props}
  />
));

Input.displayName = "Input";

export { Input };