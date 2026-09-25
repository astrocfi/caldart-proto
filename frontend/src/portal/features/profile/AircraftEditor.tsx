/**
 * Editing an aircraft from the member's own screen.
 *
 * `AircraftPermission` lets the member who added an airplane keep it up to
 * date.  This is the same `<AircraftForm/>` the administrator uses, without
 * the administrator's own fields (notes, in-service), and only for a record
 * this member created; anyone else's shows who to ask instead.
 */
import { useAircraft, useUpdateAircraft } from '@/portal/features/aircraft';
import { AircraftForm } from '@/portal/features/aircraft';
import { aircraftToValues } from '@/portal/features/aircraft';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { AircraftPatch } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { useToast } from '@/portal/components/Toast';

export interface AircraftEditorProps {
  aircraftId: number;
  /** The signed-in member, to tell their own records from everyone else's. */
  userId: number | null;
  onClose: () => void;
  onSaved: () => void;
}

/** Edits an aircraft the signed-in member added; shows who to ask for any other record. */
export function AircraftEditor({
  aircraftId,
  userId,
  onClose: handleClose,
  onSaved,
}: AircraftEditorProps): JSX.Element {
  const aircraft = useAircraft(aircraftId);
  const update = useUpdateAircraft(aircraftId);
  const toast = useToast();

  if (aircraft.isPending) {
    return (
      <Card title="Edit aircraft">
        <p className="muted" role="status">
          Loading the record…
        </p>
      </Card>
    );
  }

  if (aircraft.isError || !aircraft.data) {
    return (
      <Card title="Edit aircraft">
        <EmptyState
          title="That aircraft could not be loaded"
          description={
            aircraft.error instanceof ApiError
              ? aircraft.error.message
              : 'Something went wrong. Try again in a moment.'
          }
          action={<Button onClick={handleClose}>Close</Button>}
        />
      </Card>
    );
  }

  const record = aircraft.data;
  const mine = userId !== null && record.created_by === userId;

  if (!mine) {
    return (
      <Card eyebrow="Edit" title={record.n_number}>
        <EmptyState
          title="Someone else added this aircraft"
          description="Ask a CalDART account administrator to correct it."
          action={<Button onClick={handleClose}>Close</Button>}
        />
      </Card>
    );
  }

  const serverErrors = update.error instanceof ApiError ? update.error.fieldErrors : undefined;

  return (
    <Card eyebrow="Edit" title={record.n_number}>
      <AircraftForm
        initial={aircraftToValues(record)}
        submitLabel="Save aircraft"
        pending={update.isPending}
        serverErrors={serverErrors}
        onCancel={handleClose}
        onSubmit={(payload: AircraftPatch) =>
          update.mutate(payload, {
            onSuccess: () => {
              toast.show(`${record.n_number} updated.`, 'success');
              onSaved();
            },
            onError: (error) =>
              toast.show(
                error instanceof ApiError ? error.message : `${record.n_number} was not saved.`,
                'error',
              ),
          })
        }
      />
    </Card>
  );
}
