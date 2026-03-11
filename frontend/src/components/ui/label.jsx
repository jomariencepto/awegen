import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
import { cva } from "class-variance-authority";
import { cn } from "../../utils";
import "./css/label.css";

const labelVariants = cva("label");

const Label = React.forwardRef(({ className, ...props }, ref) => (
  <LabelPrimitive.Root 
    ref={ref} 
    className={cn(labelVariants(), className)} 
    {...props} 
  />
));

Label.displayName = "Label";

export { Label };