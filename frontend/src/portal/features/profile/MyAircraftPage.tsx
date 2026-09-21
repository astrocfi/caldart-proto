/**
 * `/profile/aircraft` — the planes a member commonly flies.
 *
 * The search half is `<AircraftPicker/>` from `@/portal/features/aircraft`;
 * this page attaches and detaches what it hands back, opens `<AircraftEditor/>`
 * on an attached aircraft, and shows the insurance currency a DART leader will
 * check.
 */
import { AircraftPicker } from '@/portal/features/aircraft';
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '../../api/client';
import type { AircraftSummary } from '../../api/types';
import { ButtonLink, Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { Page } from '../../components/Page';
import { CurrencyChip } from '../../components/StatusChip';
import { useToast } from '../../components/Toast';
import { useAuth } from '../../auth/useAuth';
import { AircraftEditor } from './AircraftEditor';
import { useAttachAircraft, useDetachAircraft, useProfile } from './api';
import './profile.css';

/** Renders, attaches and detaches the planes on the signed-in member's profile. */
export function MyAircraftPage(): JSX.Element {
  const profile = useProfile();
  const attach = useAttachAircraft();
  const detach = useDetachAircraft();
  const toast = useToast();
  const { user } = useAuth();
  // The record open for editing, if any.  A member may correct an aeroplane
  // they added themselves.
  const [editing, setEditing] = useState<number | null>(null);

  const aircraft: AircraftSummary[] = profile.data?.aircraft ?? [];
  const busy = attach.isPending || detach.isPending;

  function fail(error: unknown, fallback: string) {
    toast.show(error instanceof ApiError ? error.message : fallback, 'error');
  }

  return (
    <Page
      title="My aircraft"
      eyebrow="Membership"
      lede="The planes you commonly fly. DART leaders check the insurance on these before a mission."
      actions={
        <ButtonLink to="/profile" variant="secondary">
          Back to profile
        </ButtonLink>
      }
    >
      <Card title="Attached aircraft">
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
              <li key={plane.id} className="aircraft-list__item">
                <span className="aircraft-list__ident">{plane.n_number}</span>
                <span>{[plane.make, plane.model].filter(Boolean).join(' ') || 'Unknown type'}</span>
                <CurrencyChip
                  isCurrent={plane.insurance_is_current}
                  missing={plane.insurance_expiration === null}
                />
                <p className="aircraft-list__meta">{plane.insurance_summary}</p>
                <span className="aircraft-list__actions">
                  <Button
                    variant="quiet"
                    small
                    disabled={busy}
                    onClick={() => setEditing((open) => (open === plane.id ? null : plane.id))}
                  >
                    {editing === plane.id ? 'Close' : 'Edit'}
                  </Button>
                  <Button
                    variant="quiet"
                    small
                    disabled={busy}
                    onClick={() =>
                      detach.mutate(plane.id, {
                        onSuccess: () => toast.show(`${plane.n_number} removed.`, 'success'),
                        onError: (error) => fail(error, `${plane.n_number} was not removed.`),
                      })
                    }
                  >
                    Remove
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {editing !== null ? (
        <AircraftEditor
          aircraftId={editing}
          userId={user?.id ?? null}
          onClose={() => setEditing(null)}
          onSaved={() => setEditing(null)}
        />
      ) : null}

      <AircraftPicker
        excludeIds={aircraft.map((plane) => plane.id)}
        onSelect={(selected) =>
          attach.mutate(selected.id, {
            onSuccess: () => toast.show(`${selected.n_number} added.`, 'success'),
            onError: (error) => fail(error, `${selected.n_number} was not added.`),
          })
        }
      />
    </Page>
  );
}
