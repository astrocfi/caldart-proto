/**
 * A tiny toast queue.  Wrap the app in `<ToastProvider>` and call
 * `useToast().show(...)` from anywhere.
 *
 * The toast is the portal's one way of confirming that a save, a send, or a delete went
 * through, and of saying that one did not when the screen has no field to show it beside.
 */
import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import type { JSX, ReactNode } from 'react';

export type ToastTone = 'info' | 'success' | 'error';

export interface Toast {
  id: number;
  message: string;
  tone: ToastTone;
}

export interface ToastApi {
  show: (message: string, tone?: ToastTone) => void;
  dismiss: (id: number) => void;
  toasts: Toast[];
}

const ToastContext = createContext<ToastApi | null>(null);

export const TOAST_TIMEOUT_MS = 6000;

/** Provides the toast queue and renders its viewport above `children`. */
export function ToastProvider({ children }: { children: ReactNode }): JSX.Element {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback(
    (message: string, tone: ToastTone = 'info') => {
      const id = nextId.current++;
      setToasts((current) => [...current, { id, message, tone }]);
      window.setTimeout(() => dismiss(id), TOAST_TIMEOUT_MS);
    },
    [dismiss],
  );

  const value = useMemo<ToastApi>(() => ({ show, dismiss, toasts }), [show, dismiss, toasts]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={(id) => dismiss(id)} />
    </ToastContext.Provider>
  );
}

/** Reads the toast queue from context; throws outside a `<ToastProvider>`. */
export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used inside a <ToastProvider>');
  return context;
}

/**
 * Renders the queued toasts, or nothing when the queue is empty: a polite `status`
 * region, inside which an `error` toast is an `alert` of its own.
 */
export function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: Toast[];
  onDismiss: (id: number) => void;
}): JSX.Element | null {
  if (toasts.length === 0) return null;
  return (
    <div className="toast-viewport" role="status" aria-live="polite">
      {toasts.map((toast) => (
        // A failure is announced at once; a success or a note waits its turn.
        <div
          key={toast.id}
          className={`toast toast--${toast.tone}`}
          role={toast.tone === 'error' ? 'alert' : undefined}
        >
          <span>{toast.message}</span>
          <button
            type="button"
            className="toast__close"
            aria-label="Dismiss"
            onClick={() => onDismiss(toast.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
