/**
 * A "coming soon" page for a portal route whose screen is not built yet.  No
 * route uses it at present.
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

/** Shorthand for a route's `element`. */
export function comingSoon(feature: string, branch: string) {
  return <ComingSoon feature={feature} branch={branch} />;
}
