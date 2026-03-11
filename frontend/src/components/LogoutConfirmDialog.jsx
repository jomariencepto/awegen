import React, { useEffect } from 'react';
import { Button } from './ui/button';

function LogoutConfirmDialog({
  open,
  onCancel,
  onConfirm,
  title = 'Confirm Logout',
  message = 'Are you sure you want to log out?',
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  isProcessing = false
}) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !isProcessing) {
        onCancel?.();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onCancel, isProcessing]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/50"
        onClick={() => {
          if (!isProcessing) onCancel?.();
        }}
        aria-label="Close logout confirmation dialog"
      />

      <div
        className="relative w-full max-w-sm rounded-xl border border-amber-200 bg-white p-5 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="logout-confirm-title"
      >
        <h2 id="logout-confirm-title" className="text-lg font-semibold text-gray-900">
          {title}
        </h2>
        <p className="mt-2 text-sm text-gray-600">{message}</p>

        <div className="mt-5 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isProcessing}
            className="border-gray-300 text-gray-700"
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            onClick={onConfirm}
            disabled={isProcessing}
            className="bg-red-600 text-white hover:bg-red-700"
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default LogoutConfirmDialog;
