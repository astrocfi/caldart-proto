import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@test/render';
import { RecoveryCodesPanel, codesText } from './RecoveryCodesPanel';

const CODES = ['abcde-fghjk', 'mnpqr-stuvw'];

/** What `blob` holds, read as text the way jsdom's Blob allows. */
function blobText(blob: Blob | undefined): Promise<string> {
  return new Promise((resolve, reject) => {
    if (blob === undefined) {
      reject(new Error('Nothing was downloaded.'));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '');
    reader.onerror = () => reject(new Error('The download could not be read.'));
    reader.readAsText(blob);
  });
}

describe('codesText', () => {
  it('puts one code on each line after a line about them', () => {
    expect(codesText(CODES).split('\n').slice(2, 4)).toEqual(CODES);
  });
});

describe('<RecoveryCodesPanel/>', () => {
  it('lists every code', () => {
    const handleDone = vi.fn();
    renderWithProviders(<RecoveryCodesPanel codes={CODES} onDone={handleDone} />);
    expect(screen.getAllByRole('listitem').map((item) => item.textContent)).toEqual(CODES);
  });

  it('copies the codes, one per line', async () => {
    const user = userEvent.setup();
    const handleDone = vi.fn();
    renderWithProviders(<RecoveryCodesPanel codes={CODES} onDone={handleDone} />);
    await user.click(screen.getByRole('button', { name: 'Copy' }));

    expect(await screen.findByText('Copied.')).toBeInTheDocument();
    expect(await navigator.clipboard.readText()).toBe('abcde-fghjk\nmnpqr-stuvw');
  });

  it('downloads the codes as a text file and lets the link go afterward', async () => {
    const created: Blob[] = [];
    const create = vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
      created.push(blob as Blob);
      return 'blob:codes';
    });
    const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    // jsdom cannot follow the download link, so the click is only recorded.
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);
    const handleDone = vi.fn();
    renderWithProviders(<RecoveryCodesPanel codes={CODES} onDone={handleDone} />);
    await userEvent.click(screen.getByRole('button', { name: 'Download as .txt' }));

    expect(await blobText(created[0])).toBe(codesText(CODES));
    await waitFor(() => expect(revoke).toHaveBeenCalledWith('blob:codes'), { timeout: 3000 });
    expect(click).toHaveBeenCalledOnce();
    create.mockRestore();
    revoke.mockRestore();
    click.mockRestore();
  });

  it('moves on only when the person says they saved them', async () => {
    const handleDone = vi.fn();
    renderWithProviders(<RecoveryCodesPanel codes={CODES} onDone={handleDone} />);
    await userEvent.click(screen.getByRole('button', { name: 'I saved these' }));

    expect(handleDone).toHaveBeenCalledOnce();
  });
});
