/**
 * `/profile/aircraft` — the planes a member commonly flies.
 *
 * The search half is `<AircraftPicker/>` from `@/portal/features/aircraft`;
 * this page attaches and detaches what it hands back, opens `<AircraftEditor/>`
 * on an attached aircraft, and shows the insurance currency a DART leader will
 * check and whether an authority has verified the policy (no mark while no policy
 * is on file, since there is nothing to verify).  The coverage
 * policy's note to members stands above the list, and an aircraft the policy
 * excludes is marked with the reason.
 */
import { AircraftPicker, useCoveragePolicy } from '@/portal/features/aircraft';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { ButtonLink, Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DeleteButton } from '@/portal/components/DeleteButton';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { CurrencyDot, StatusDot } from '@/portal/components/StatusDot';
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
  // The record open for editing, if any.  A member may correct an airplane
  // they added themselves.
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
      actions={
        <ButtonLink to="/profile" variant="secondary">
          Back to profile
        </ButtonLink>
      }
    >
      <Card title="Attached aircraft">
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
                <CurrencyDot
                  isCurrent={plane.insurance_is_current}
                  missing={plane.insurance_expiration === null}
                />
                {plane.insurance_expiration === null && !plane.insurance_verified ? null : (
                  // With no policy on file there is nothing to verify yet, so no mark.
                  <VerifiedMark verification={{ verified: plane.insurance_verified }} pending />
                )}
                {plane.coverage.excluded ? <StatusDot tone="expired" label="Not covered" /> : null}
                <p className="aircraft-list__meta">
                  {plane.coverage.excluded
                    ? `${plane.insurance_summary} · ${plane.coverage.reason}`
                    : plane.insurance_summary}
                </p>
                <span className="aircraft-list__actions">
                  <Button
                    variant="quiet"
                    small
                    disabled={busy}
                    onClick={() => setEditing((open) => (open === plane.id ? null : plane.id))}
                  >
                    {editing === plane.id ? 'Close' : 'Edit'}
                  </Button>
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
            userId={user?.id ?? null}
            isAccountAdmin={user?.roles.includes('account_admin') ?? false}
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
