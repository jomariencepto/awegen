export const STATUS_POPUP_EVENT = 'awegen:status-popup';

const PATCH_FLAG = '__awegen_status_popup_patched__';
const ORIGINALS_KEY = '__awegen_status_popup_originals__';

let popupSequence = 0;

const nextPopupId = (prefix) => {
  popupSequence += 1;
  return `${prefix}-popup-${Date.now()}-${popupSequence}`;
};

const normalizeMessage = (input, fallback) => {
  if (typeof input === 'string' && input.trim()) {
    return input.trim();
  }
  if (input && typeof input.message === 'string' && input.message.trim()) {
    return input.message.trim();
  }
  return fallback;
};

export const emitStatusPopup = ({
  type = 'success',
  title,
  message,
  confirmLabel = 'Confirm',
  onConfirm = null,
} = {}) => {
  if (typeof window === 'undefined') return;

  window.dispatchEvent(
    new CustomEvent(STATUS_POPUP_EVENT, {
      detail: {
        id: nextPopupId(type),
        type,
        title: title || (type === 'success' ? 'Success!' : 'Error!'),
        message: message || (type === 'success'
          ? 'Action completed successfully.'
          : 'Something went wrong.'),
        confirmLabel,
        onConfirm,
      },
    })
  );
};

export const patchToastForStatusPopup = (toastObj) => {
  if (!toastObj || toastObj[PATCH_FLAG]) {
    return () => {};
  }

  const originals = {
    success: toastObj.success,
    error: toastObj.error,
  };

  toastObj[ORIGINALS_KEY] = originals;
  toastObj[PATCH_FLAG] = true;

  toastObj.success = (message, options = {}) => {
    if (options?.id) {
      toastObj.dismiss(options.id);
    }

    emitStatusPopup({
      type: 'success',
      title: options?.title || 'Success!',
      message: normalizeMessage(message, 'Action completed successfully.'),
      confirmLabel: options?.confirmLabel || 'Confirm',
    });

    return options?.id || nextPopupId('success');
  };

  toastObj.error = (message, options = {}) => {
    if (options?.id) {
      toastObj.dismiss(options.id);
    }

    emitStatusPopup({
      type: 'error',
      title: options?.title || 'Error!',
      message: normalizeMessage(message, 'Something went wrong.'),
      confirmLabel: options?.confirmLabel || 'Confirm',
    });

    return options?.id || nextPopupId('error');
  };

  return () => {
    if (!toastObj || !toastObj[PATCH_FLAG]) {
      return;
    }

    const savedOriginals = toastObj[ORIGINALS_KEY];
    if (savedOriginals?.success) {
      toastObj.success = savedOriginals.success;
    }
    if (savedOriginals?.error) {
      toastObj.error = savedOriginals.error;
    }

    delete toastObj[ORIGINALS_KEY];
    delete toastObj[PATCH_FLAG];
  };
};
