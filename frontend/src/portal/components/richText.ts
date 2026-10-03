/**
 * Pure helpers behind `RichTextEditor`: reading the address a sender typed for a
 * link, and the size an inserted image is shown at in an email.
 */

/** The widest an image is shown in an email, in pixels: the width of the message. */
export const EMAIL_IMAGE_WIDTH = 600;

/** A leading URL scheme such as `https:` or `mailto:`. */
const SCHEME = /^([a-z][a-z\d+.-]*):/i;

/** The schemes a link may use; the server refuses any other. */
const LINK_SCHEMES = new Set(['http', 'https', 'mailto']);

/** Something shaped like an email address, with nothing around it. */
const EMAIL_ADDRESS = /^[^\s@/]+@[^\s@/]+\.[^\s@/]+$/;

/**
 * The address a link goes to, read from what the sender typed, or `null` when it
 * cannot be a link.
 *
 * Surrounding spaces are dropped.  An address with `http:`, `https:`, or `mailto:`
 * in front is taken as typed.  An email address on its own gains `mailto:`, and
 * anything else without a scheme -- `caldart.org/events` -- gains `https://`, since
 * a sender rarely types the scheme.  Blank text, text with a space in it, and any
 * other scheme, such as `javascript:`, answer `null`.
 *
 * @param typed what the sender typed in the link's address box.
 * @returns the address to link to, or `null`.
 */
export function linkAddress(typed: string): string | null {
  const address = typed.trim();
  if (address === '' || /\s/.test(address)) return null;
  const scheme = SCHEME.exec(address)?.[1]?.toLowerCase();
  if (scheme === undefined || scheme.includes('.')) {
    // No scheme at all, or a host with a port (`caldart.org:8080`) read as one.
    return EMAIL_ADDRESS.test(address) ? `mailto:${address}` : `https://${address}`;
  }
  return LINK_SCHEMES.has(scheme) ? address : null;
}

/** The width and height an image is shown at. */
export interface ImageSize {
  width: number;
  height: number;
}

/**
 * The size an image `width` by `height` pixels is shown at in an email: its own
 * size, or scaled down to `EMAIL_IMAGE_WIDTH` wide with its proportions kept.
 *
 * Some mail programs ignore a style sheet's width limit and honor only the image's
 * own `width` and `height`, so the editor writes these into the message.
 *
 * @returns whole pixels, never less than one.
 */
export function emailImageSize(width: number, height: number): ImageSize {
  if (width <= EMAIL_IMAGE_WIDTH) return { width, height };
  return {
    width: EMAIL_IMAGE_WIDTH,
    height: Math.max(1, Math.round((height * EMAIL_IMAGE_WIDTH) / width)),
  };
}
