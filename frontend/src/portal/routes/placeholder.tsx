/**
 * Placeholder pages so every route in PLAN §8 resolves from day one.
 *
 * Phase 2 branches replace the `element` in their own `routes/*.tsx` file with
 * the real feature component; nothing else has to change.
 */
import { Card } from '../components/Card';
import { Page } from '../components/Page';

export interface ComingSoonProps {
  feature: string;
  branch: string;
}

export function ComingSoon({ feature, branch }: ComingSoonProps) {
  return (
    <Page title={feature} eyebrow="Not built yet">
      <Card>
        <p>Coming soon: {feature}</p>
        <p className="muted">
          This screen is delivered by <code className="mono">{branch}</code>.
        </p>
      </Card>
    </Page>
  );
}

/** Shorthand used by every stub route. */
export function comingSoon(feature: string, branch: string) {
  return <ComingSoon feature={feature} branch={branch} />;
}
