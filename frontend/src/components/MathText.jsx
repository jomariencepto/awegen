import React from 'react';
import { InlineMath, BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';

const DELIMITED_MATH_RE = /(\$\$[\s\S]+?\$\$|\$[^$\n]+\$)/g;
const STANDALONE_MATH_RE =
  /^[0-9A-Za-z\s()+\-*/=^_.,:%[\]{}|<>/\\\u00b1\u03a9\u03b1\u03b2\u03b3\u03b4\u03b8\u03bb\u03bc\u03c0\u03c3\u2211\u221a\u221e\u222b\u2264\u2265]+$/u;
const MATH_SYMBOL_RE =
  /[=+\-*/^_<>]|\b(?:sin|cos|tan|log|ln)\b|[\u00b1\u03a9\u03b1\u03b2\u03b3\u03b4\u03b8\u03bb\u03bc\u03c0\u03c3\u2211\u221a\u221e\u222b\u2264\u2265]/iu;
const NATURAL_LANGUAGE_WORD_RE = /\b[A-Za-z]{4,}\b/;

function looksLikeStandaloneMath(text) {
  const normalized = (text || '').trim();
  if (!normalized || normalized.includes('$')) {
    return false;
  }

  if (normalized.length > 120) {
    return false;
  }

  if (!STANDALONE_MATH_RE.test(normalized)) {
    return false;
  }

  if (NATURAL_LANGUAGE_WORD_RE.test(normalized)) {
    return false;
  }

  return MATH_SYMBOL_RE.test(normalized);
}

function MathText({ text, className = '' }) {
  if (!text) return null;

  if (looksLikeStandaloneMath(text)) {
    return <InlineMath math={text} />;
  }

  const parts = text.split(DELIMITED_MATH_RE);

  return (
    <span className={className}>
      {parts.map((part, i) => {
        if (part.startsWith('$$') && part.endsWith('$$')) {
          return <BlockMath key={i} math={part.slice(2, -2)} />;
        }

        if (part.startsWith('$') && part.endsWith('$')) {
          return <InlineMath key={i} math={part.slice(1, -1)} />;
        }

        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}

export default MathText;
