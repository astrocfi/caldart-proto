/**
 * The aircraft categories and airworthiness classifications, in the order every
 * screen lists them, with the words each one reads as.
 */
import type { AircraftCategory, Airworthiness } from '@/portal/api/types';

export const CATEGORY_LABELS: Record<AircraftCategory, string> = {
  airplane: 'Airplane',
  helicopter: 'Helicopter',
  gyroplane: 'Gyroplane',
  glider: 'Glider',
  balloon: 'Balloon',
  airship: 'Airship',
  powered_lift: 'Powered lift',
  weight_shift: 'Weight-shift control',
  powered_parachute: 'Powered parachute',
  other: 'Other',
};

export const CATEGORIES = Object.keys(CATEGORY_LABELS) as AircraftCategory[];

export const AIRWORTHINESS_LABELS: Record<Airworthiness, string> = {
  standard: 'Standard',
  limited: 'Limited',
  restricted: 'Restricted',
  experimental: 'Experimental',
  provisional: 'Provisional',
  multiple: 'Multiple',
  primary: 'Primary',
  special_flight_permit: 'Special flight permit',
  light_sport: 'Light sport',
};

export const AIRWORTHINESS_VALUES = Object.keys(AIRWORTHINESS_LABELS) as Airworthiness[];

/** What the aircraft check says of an aircraft with no category. */
const CATEGORY_NOT_RECORDED = 'Category not recorded';

/** What a blank category or airworthiness reads as. */
export const NOT_RECORDED = 'Not recorded';

/**
 * The category and airworthiness as one line, e.g. `Helicopter · Standard`.  A
 * blank category reads `Category not recorded`, as the coverage check says it
 * (`Category not recorded · Standard`); a blank airworthiness is left out.
 */
export function categoryLine({
  category,
  airworthiness,
}: {
  category: AircraftCategory | '';
  airworthiness: Airworthiness | '';
}): string {
  const categoryPart = category === '' ? CATEGORY_NOT_RECORDED : CATEGORY_LABELS[category];
  return airworthiness === ''
    ? categoryPart
    : `${categoryPart} · ${AIRWORTHINESS_LABELS[airworthiness]}`;
}
