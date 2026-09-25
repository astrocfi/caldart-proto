/**
 * Change what a standing authority charges: the plan, and the contribution.
 *
 * It offers the same choosers the setup flow does, so a member changes their
 * mind in the words they made it up in.  The dues themselves are not settable:
 * every charge takes the chosen plan's price on the day.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { RenewalMandate, RenewalPatchRequest } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { EmptyState } from '@/portal/components/EmptyState';
import { formatCents } from '@/portal/components/Money';
import { useToast } from '@/portal/components/Toast';
import { ContributionChooser } from '@/portal/features/checkout/ContributionChooser';
import { PlanChooser } from '@/portal/features/checkout/PlanChooser';
import { usePaymentsConfig } from '@/portal/features/checkout/api';
import { useUpdateRenewal } from './api';
import '@/portal/features/checkout/checkout.css';

export interface RenewalChangeFormProps {
  mandate: RenewalMandate;
  /** True for a life member: their membership does not renew, so no plan is offered. */
  isLifetime: boolean;
  /** Called once the change is saved, or abandoned. */
  onDone: () => void;
}

/** The plan and contribution choosers over a mandate, saved with `PATCH /me/renewal`. */
export function RenewalChangeForm({
  mandate,
  isLifetime,
  onDone: handleDone,
}: RenewalChangeFormProps): JSX.Element {
  const { data: config, isPending } = usePaymentsConfig();
  const [plan, setPlan] = useState<string | null>(mandate.plan);
  const [contributionCents, setContributionCents] = useState(mandate.contribution_cents);
  const [isOther, setIsOther] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const update = useUpdateRenewal();
  const toast = useToast();

  if (isPending) {
    return (
      <p className="muted" role="status">
        Loading payment options…
      </p>
    );
  }

  if (!config) {
    return (
      <EmptyState
        title="Payment options could not be loaded"
        description="Please reload the page, or contact CalDART if it keeps happening."
      />
    );
  }

  // A membership that never expires cannot renew itself, so it is never offered.
  const renewable = config.plans.filter((entry) => entry.duration_days !== null);
  const offered = renewable.map((entry) => entry.slug);
  const chosenPlan = plan !== null && offered.includes(plan) ? plan : (offered[0] ?? null);

  async function save(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    const request: RenewalPatchRequest = { contribution_cents: contributionCents };
    if (!isLifetime && chosenPlan !== null) request.plan = chosenPlan;
    try {
      await update.mutateAsync(request);
      toast.show('Contribution saved.', 'success');
      handleDone();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? (caught.fieldErrors.contribution_cents ??
              caught.fieldErrors.plan ??
              caught.fieldErrors.auto_renew ??
              caught.message)
          : 'That change could not be saved.',
      );
    }
  }

  const planCents = renewable.find((entry) => entry.slug === chosenPlan)?.price_cents ?? 0;
  const chargeCents = isLifetime ? contributionCents : planCents + contributionCents;

  return (
    <form className="renewal__change stack" onSubmit={(event) => void save(event)}>
      {isLifetime || chosenPlan === null ? null : (
        <PlanChooser plans={renewable} value={chosenPlan} onChange={(next) => setPlan(next)} />
      )}

      <ContributionChooser
        tiers={config.contribution_tiers}
        value={contributionCents}
        maxCents={config.max_contribution_cents}
        onChange={(next) => setContributionCents(next)}
        isOther={isOther}
        // codespell:ignore-next-line onother
        onOther={(next) => {
          setIsOther(next);
          if (next) setContributionCents(0);
        }}
      />

      <p className="renewal-setup__total">
        Each year CalDART will charge <strong className="mono">{formatCents(chargeCents)}</strong>
        {isLifetime
          ? ' for your contribution.'
          : ' — the plan price on the day, plus your contribution.'}
      </p>

      {error ? (
        <p className="renewal__error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="cluster">
        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? 'Saving…' : 'Save changes'}
        </Button>
        <Button variant="quiet" onClick={handleDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
