import { act, fireEvent, render, renderHook, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TOAST_TIMEOUT_MS, ToastProvider, ToastViewport, useToast } from './Toast';
import type { ToastTone } from './Toast';

/** A button per tone, so a test can raise a toast the way a screen does. */
function Raiser({ message, tone }: { message: string; tone?: ToastTone }) {
  const { show } = useToast();
  return (
    <button type="button" onClick={() => show(message, tone)}>
      raise {message}
    </button>
  );
}

function wrapper({ children }: { children: ReactNode }) {
  return <ToastProvider>{children}</ToastProvider>;
}

describe('ToastProvider', () => {
  it('renders nothing until a toast is raised', () => {
    render(<Raiser message="Saved." />, { wrapper });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('shows the message that was raised', async () => {
    const user = userEvent.setup();
    render(<Raiser message="Profile saved." />, { wrapper });

    await user.click(screen.getByRole('button', { name: 'raise Profile saved.' }));

    expect(screen.getByRole('status')).toHaveTextContent('Profile saved.');
  });

  it('announces politely, so a screen reader does not interrupt', async () => {
    const user = userEvent.setup();
    render(<Raiser message="Profile saved." />, { wrapper });

    await user.click(screen.getByRole('button', { name: 'raise Profile saved.' }));

    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
  });

  it.each<[ToastTone | undefined, string]>([
    [undefined, 'toast toast--info'],
    ['info', 'toast toast--info'],
    ['success', 'toast toast--success'],
    ['error', 'toast toast--error'],
  ])('renders the %s tone', async (tone, expected) => {
    const user = userEvent.setup();
    render(<Raiser message="Done." tone={tone} />, { wrapper });

    await user.click(screen.getByRole('button', { name: 'raise Done.' }));

    expect(screen.getByText('Done.').parentElement).toHaveClass(expected, { exact: true });
  });

  it('queues a second toast beside the first, oldest first', async () => {
    const user = userEvent.setup();
    render(
      <>
        <Raiser message="First." />
        <Raiser message="Second." />
      </>,
      { wrapper },
    );

    await user.click(screen.getByRole('button', { name: 'raise First.' }));
    await user.click(screen.getByRole('button', { name: 'raise Second.' }));

    expect(screen.getByRole('status').textContent).toBe('First.×Second.×');
  });

  it('dismisses one toast from its own close button and leaves the other', async () => {
    const user = userEvent.setup();
    render(
      <>
        <Raiser message="First." />
        <Raiser message="Second." />
      </>,
      { wrapper },
    );
    await user.click(screen.getByRole('button', { name: 'raise First.' }));
    await user.click(screen.getByRole('button', { name: 'raise Second.' }));

    await user.click(screen.getAllByRole('button', { name: 'Dismiss' })[0]!);

    expect(screen.queryByText('First.')).not.toBeInTheDocument();
    expect(screen.getByText('Second.')).toBeInTheDocument();
  });

  describe('on a fake clock', () => {
    // No `shouldAdvanceTime`: the clock must move only when a test moves it,
    // or the assertion one millisecond short of the timeout is a coin toss.
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('drops the toast on its own after the timeout', async () => {
      render(<Raiser message="Backup started." />, { wrapper });
      act(() => {
        fireEvent.click(screen.getByRole('button', { name: 'raise Backup started.' }));
      });
      expect(screen.getByText('Backup started.')).toBeInTheDocument();

      await act(() => vi.advanceTimersByTimeAsync(TOAST_TIMEOUT_MS - 1));
      expect(screen.getByText('Backup started.')).toBeInTheDocument();

      await act(() => vi.advanceTimersByTimeAsync(1));
      expect(screen.queryByText('Backup started.')).not.toBeInTheDocument();
    });
  });
});

describe('ToastViewport', () => {
  it('renders nothing for an empty queue', () => {
    const { container } = render(<ToastViewport toasts={[]} onDismiss={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('hands the dismissed toast id back to its caller', async () => {
    const user = userEvent.setup();
    const handleDismiss = vi.fn();
    render(
      <ToastViewport
        toasts={[{ id: 9, message: 'Sent.', tone: 'success' }]}
        onDismiss={handleDismiss}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Dismiss' }));

    expect(handleDismiss).toHaveBeenCalledWith(9);
  });
});

describe('useToast', () => {
  it('refuses to work outside a ToastProvider', () => {
    expect(() => renderHook(() => useToast())).toThrow(
      'useToast must be used inside a <ToastProvider>',
    );
  });
});
