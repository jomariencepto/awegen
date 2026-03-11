import React from 'react';
import { InlineMath, BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';

// Detects Unicode math characters and caret-exponent notation
const MATH_CHARS = /[∑∫√πμσα β±≤≥∂²³₀₁₂₃ᵢ]|[A-Za-z]\^/;

/**
 * Renders a string that may contain math formulas.
 *
 * Supported formats:
 *   $$...$$ → block (display) math via KaTeX
 *   $...$   → inline math via KaTeX
 *   plain Unicode math (μ, σ, √, etc.) → attempted inline KaTeX render
 *   plain text → rendered as-is in a <span>
 */
function MathText({ text, className = '' }) {
  if (!text) return null;

  // If no $ delimiters but the string contains math symbols,
  // try rendering the whole string as inline KaTeX.
  if (!text.includes('$') && MATH_CHARS.test(text)) {
    try {
      return <InlineMath math={text} />;
    } catch {
      // KaTeX couldn't parse it — fall back to plain text
      return <span className={className}>{text}</span>;
    }
  }

  // Split on $$...$$ and $...$ delimiters, preserving the delimiters
  const parts = text.split(/(\$\$[^$]+\$\$|\$[^$]+\$)/g);

  return (
    <span className={className}>
      {parts.map((part, i) => {
        if (part.startsWith('$$') && part.endsWith('$$')) {
          try {
            return <BlockMath key={i} math={part.slice(2, -2)} />;
          } catch {
            return <span key={i}>{part}</span>;
          }
        }
        if (part.startsWith('$') && part.endsWith('$')) {
          try {
            return <InlineMath key={i} math={part.slice(1, -1)} />;
          } catch {
            return <span key={i}>{part}</span>;
          }
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}

export default MathText;
