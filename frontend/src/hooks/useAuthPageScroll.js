import { useEffect } from 'react';

export default function useAuthPageScroll() {
  useEffect(() => {
    if (typeof document === 'undefined') return undefined;

    const html = document.documentElement;
    const body = document.body;
    const root = document.getElementById('root');
    const elements = [html, body, root].filter(Boolean);
    const previousStyles = elements.map((element) => ({
      element,
      overflow: element.style.overflow,
      overflowY: element.style.overflowY,
      overflowX: element.style.overflowX,
    }));

    elements.forEach((element) => {
      element.style.overflow = 'auto';
      element.style.overflowY = 'auto';
      element.style.overflowX = 'hidden';
    });

    return () => {
      previousStyles.forEach(({ element, overflow, overflowY, overflowX }) => {
        element.style.overflow = overflow;
        element.style.overflowY = overflowY;
        element.style.overflowX = overflowX;
      });
    };
  }, []);
}
