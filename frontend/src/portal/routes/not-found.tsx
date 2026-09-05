import { ButtonLink } from '../components/Button';
import { EmptyState } from '../components/EmptyState';
import { Page } from '../components/Page';

export function NotFound() {
  return (
    <Page title="Page not found" eyebrow="404">
      <EmptyState
        title="That page is not part of the member portal"
        description="Check the address, or head back to your dashboard."
        action={<ButtonLink to="/">Go to the dashboard</ButtonLink>}
      />
    </Page>
  );
}
