/**
 * Shared aircraft search-and-attach control.
 *
 * `feat/aircraft-leader` implements it against `GET /aircraft` and
 * `GET /aircraft/lookup`; `feat/profile-join` only imports it for the
 * "planes I commonly fly" section of the profile form.  Keep the props stable.
 */
import type { JSX } from 'react';

import { Card } from '../../components/Card';
import type { Aircraft } from '../../api/types';

export interface AircraftPickerProps {
  onSelect: (aircraft: Aircraft) => void;
  /** Aircraft already attached, so they can be filtered out of the results. */
  excludeIds?: number[];
}

export function AircraftPicker(_props: AircraftPickerProps): JSX.Element {
  return (
    <Card eyebrow="Aircraft" title="Find an aircraft">
      <p className="muted">Aircraft search coming soon</p>
    </Card>
  );
}
