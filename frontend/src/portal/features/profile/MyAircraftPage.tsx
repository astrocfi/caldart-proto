/**
 * `/profile/aircraft` — the planes a member commonly flies.
 *
 * The search half is `<AircraftPicker/>` from `@/portal/features/aircraft`;
 * this page attaches and detaches what it hands back, opens `<AircraftEditor/>`
 * on an attached aircraft the member added (any aircraft, for an account
 * administrator), and shows the insurance a DART leader will check, in the words every
 * aircraft list uses (`InsuranceDot`, dated), with each liability limit labeled, and
 * whether an authority has verified the policy (no mark while no policy is on file,
 * since there is nothing to verify).  A plane somebody else added offers no **Edit**:
 * the line says who to write to instead, at the site's contact address.  The coverage
 * policy's note to members stands above the list, and an aircraft the policy
 * excludes is marked with the reason.
 */
import { AircraftPicker, InsuranceDot, useCoveragePolicy } from '@/portal/features/aircraft';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import { useSiteConfig } from '@/portal/api/queries';
import type { AircraftSummary } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { formatCents } from '@/portal/components/Money';
import { StatusDot } from '@/portal/components/StatusDot';
import { useToast } from '@/portal/components/Toast';
import { VerifiedMark } from '@/portal/components/VerifiedMark';
import { usePanelFocus } from '@/portal/components/focus';
import { useAuth } from '@/portal/auth/useAuth';
import { AircraftEditor } from './AircraftEditor';
import { useAttachAircraft, useDetachAircraft, useProfile } from './api';
import './profile.css';

/** Renders, attaches, and detaches the planes on the signed-in member's profile. */
export function MyAircraftPage(): JSX.Element {
  const profile = useProfile();
  const attach = useAttachAircraft();
  const detach = useDetachAircraft();
  const policy = useCoveragePolicy();
  const toast = useToast();
  const { user } = useAuth();
  const contactEmail = useSiteConfig().data?.contact_email ?? '';
  const isAccountAdmin = user?.roles.includes('account_admin') ?? false;
  // A member may correct an airplane they added; an account administrator, any.
  const canEdit = (plane: AircraftSummary): boolean =>
    isAccountAdmin || (user !== null && plane.created_by === user.id);
  // The record open for editing, if any.
  const [editing, setEditing] = useState<number | null>(null);
  const handleCloseEditor = useCallback(() => setEditing(null), []);
  const editorRef = usePanelFocus(editing === null ? null : `edit-${editing}`, handleCloseEditor);
  // The plane just added, whose line takes the focus once the list shows it.
  const [addedId, setAddedId] = useState<number | null>(null);
  const itemRefs = useRef(new Map<number, HTMLLIElement | null>());

  const aircraft = profile.data?.aircraft ?? [];
  const policyNote = policy.data?.note ?? '';
  const busy = attach.isPending || detach.isPending;

  useEffect(() => {
    if (addedId === null) return;
    const item = itemRefs.current.get(addedId);
    if (item === null || item === undefined) return;
    setAddedId(null);
    item.tabIndex = -1;
    item.focus();
  }, [addedId, profile.data]);

  function fail(error: unknown, fallback: string) {
    toast.show(error instanceof ApiError ? error.message : fallback, 'error');
  }

  return (
    <Page
      title="My aircraft"
      lede="The planes you commonly fly."
      actions={<Link to="/profile">Back to My profile</Link>}
    >
      <Card title="Your aircraft">
        {policyNote === '' ? null : (
          <p className="aircraft-coverage-note" role="note" aria-label="Coverage policy">
            {policyNote}
          </p>
        )}
        {profile.isPending ? (
          <p className="muted" role="status">
            Loading your aircraft…
          </p>
        ) : aircraft.length === 0 ? (
          <EmptyState
            title="No aircraft attached yet"
            description="Search below for the aircraft you fly and add it to your profile."
          />
        ) : (
          <ul className="aircraft-list" role="list">
            {aircraft.map((plane) => (
              <li
                key={plane.id}
                className="aircraft-list__item"
                ref={(node) => {
                  itemRefs.current.set(plane.id, node);
                }}
              >
                <span className="aircraft-list__ident">{plane.n_number}</span>
                <span>{[plane.make, plane.model].filter(Boolean).join(' ') || 'Unknown type'}</span>
                <InsuranceDot aircraft={plane} withDate />
                {plane.insurance_expiration === null ? null : (
                  // With no policy on file there is nothing to verify yet, so no mark.
                  <VerifiedMark verification={{ verified: plane.insurance_verified }} pending />
                )}
                {plane.coverage.excluded ? <StatusDot tone="expired" label="Not covered" /> : null}
                <AircraftMeta plane={plane} />
                <span className="aircraft-list__actions">
                  {canEdit(plane) ? (
                    <Button
                      variant="quiet"
                      small
                      disabled={busy}
                      aria-label={`${editing === plane.id ? 'Close' : 'Edit'} ${plane.n_number}`}
                      onClick={() => setEditing((open) => (open === plane.id ? null : plane.id))}
                    >
                      {editing === plane.id ? 'Close' : 'Edit'}
                    </Button>
                  ) : (
                    <span className="aircraft-list__owner muted">
                      Added by someone else. To correct it, write to{' '}
                      {contactEmail === '' ? (
                        'CalDART'
                      ) : (
                        <a href={`mailto:${contactEmail}`}>{contactEmail}</a>
                      )}
                      .
                    </span>
                  )}
                  <DeleteButton
                    label={`Remove ${plane.n_number}`}
                    confirmLabel="Remove"
                    disabled={busy}
                    onDelete={() =>
                      detach.mutateAsync(plane.id).then(
                        () => toast.show(`${plane.n_number} removed.`, 'success'),
                        (error) => fail(error, `${plane.n_number} was not removed.`),
                      )
                    }
                  />
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {editing !== null ? (
        <div ref={editorRef}>
          <AircraftEditor
            aircraftId={editing}
            onClose={handleCloseEditor}
            onSaved={handleCloseEditor}
          />
        </div>
      ) : null}

      <AircraftPicker
        excludeIds={aircraft.map((plane) => plane.id)}
        onSelect={(selected) =>
          attach.mutate(selected.id, {
            onSuccess: () => {
              setAddedId(selected.id);
              toast.show(`${selected.n_number} added.`, 'success');
            },
            onError: (error) => fail(error, `${selected.n_number} was not added.`),
          })
        }
      />
    </Page>
  );
}

/**
 * The line under a plane: its liability limits, each labeled, such as "Liability
 * $2,000,000 per occurrence, $100,000 per person", then the reason the coverage policy
 * excludes it, if it does.  Nothing at all when neither applies.
 */
function AircraftMeta({ plane }: { plane: AircraftSummary }): JSX.Element | null {
  const parts = [liabilityLine(plane), plane.coverage.excluded ? plane.coverage.reason : ''].filter(
    (part) => part !== '',
  );
  if (parts.length === 0) return null;
  return <p className="aircraft-list__meta">{parts.join(' · ')}</p>;
}

/** The labeled liability limits, or an empty string when none is recorded. */
function liabilityLine(plane: AircraftSummary): string {
  const limits = [
    [plane.insurance_liability_per_occurrence_cents, 'per occurrence'],
    [plane.insurance_liability_per_person_cents, 'per person'],
  ] as const;
  const named = limits
    .filter(([cents]) => cents > 0)
    .map(([cents, per]) => `${formatCents(cents, { whole: true })} ${per}`);
  return named.length === 0 ? '' : `Liability ${named.join(', ')}`;
}
