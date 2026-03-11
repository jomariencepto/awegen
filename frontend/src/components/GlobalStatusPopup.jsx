import React, { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, X } from 'lucide-react';
import { STATUS_POPUP_EVENT } from '../utils/statusPopup';

function GlobalStatusPopup() {
  const [queue, setQueue] = useState([]);
  const [activePopup, setActivePopup] = useState(null);

  useEffect(() => {
    const handlePopupEvent = (event) => {
      const detail = event?.detail || {};
      setQueue((prev) => [...prev, detail]);
    };

    window.addEventListener(STATUS_POPUP_EVENT, handlePopupEvent);
    return () => window.removeEventListener(STATUS_POPUP_EVENT, handlePopupEvent);
  }, []);

  useEffect(() => {
    if (!activePopup && queue.length > 0) {
      setActivePopup(queue[0]);
      setQueue((prev) => prev.slice(1));
    }
  }, [queue, activePopup]);

  const closeAndConfirm = () => {
    if (typeof activePopup?.onConfirm === 'function') {
      try {
        activePopup.onConfirm();
      } catch {
        // no-op
      }
    }
    setActivePopup(null);
  };

  if (!activePopup) return null;

  const isSuccess = activePopup.type === 'success';
  const iconWrapperClass = isSuccess
    ? 'bg-green-100 text-green-600 ring-4 ring-green-50'
    : 'bg-red-100 text-red-600 ring-4 ring-red-50';
  const buttonClass = isSuccess
    ? 'bg-green-600 hover:bg-green-700 focus:ring-green-300'
    : 'bg-red-600 hover:bg-red-700 focus:ring-red-300';
  const topBarClass = isSuccess ? 'bg-green-500' : 'bg-red-500';

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
        <div className={`h-1.5 w-full ${topBarClass}`} />
        <div className="relative p-6 text-center">
          <button
            type="button"
            aria-label="Close popup"
            onClick={closeAndConfirm}
            className="absolute right-3 top-3 rounded-md p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>

          <div className={`mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full ${iconWrapperClass}`}>
            {isSuccess ? <CheckCircle2 className="h-9 w-9" /> : <XCircle className="h-9 w-9" />}
          </div>

          <h3 className="text-2xl font-bold text-gray-900">
            {activePopup.title || (isSuccess ? 'Success!' : 'Error!')}
          </h3>

          <p className="mt-2 whitespace-pre-line text-sm text-gray-600">
            {activePopup.message || (isSuccess ? 'Action completed successfully.' : 'Something went wrong.')}
          </p>

          <button
            type="button"
            onClick={closeAndConfirm}
            className={`mt-6 inline-flex w-full items-center justify-center rounded-md px-4 py-2 text-sm font-semibold text-white transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 ${buttonClass}`}
          >
            {activePopup.confirmLabel || 'Confirm Read'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default GlobalStatusPopup;
