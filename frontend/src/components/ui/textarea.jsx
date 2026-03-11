import * as React from "react";
import { cn } from "../../utils";
import "./css/textarea.css";

const Textarea = React.forwardRef(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn("textarea", className)}
    {...props}
  />
));

Textarea.displayName = "Textarea";

export { Textarea };