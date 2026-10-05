import type { JSX, ReactNode } from 'react';

export interface HeadingProps {
  /** The heading's level, `h2` to `h4`: one under the heading of what holds it. */
  level: 2 | 3 | 4;
  className?: string;
  children: ReactNode;
}

/**
 * A heading whose level its caller chooses, for a part drawn inside different hosts,
 * such as the checkout, which sits under a page's title in one place and under a card's
 * title in another; the level keeps the page's outline free of skipped levels.
 */
export function Heading({ level, className, children }: HeadingProps): JSX.Element {
  const Tag = `h${level}` as const;
  return <Tag className={className}>{children}</Tag>;
}
