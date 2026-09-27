/**
 * Whether the signed-in user may verify, or may grant the verifier role.
 *
 * The server decides (`IsVerifier` and the verifier endpoint's own permission);
 * these hooks only keep a button off the screen of somebody it would refuse.
 */
import type { RoleSlug } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { hasAnyRole } from '@/portal/nav';

/** The roles that verify a person's items and an aircraft's insurance. */
export const VERIFY_ROLES: readonly RoleSlug[] = [
  'verifier',
  'dart_leader',
  'user_admin',
  'account_admin',
];

/** The roles that make somebody a verifier from the member check. */
export const GRANT_VERIFIER_ROLES: readonly RoleSlug[] = ['dart_leader', 'user_admin'];

/** True when the signed-in user holds a verifying role; a system administrator always does. */
export function useCanVerify(): boolean {
  const { roles } = useAuth();
  return hasAnyRole(roles, VERIFY_ROLES);
}

/** True when the signed-in user may grant or take away the verifier role. */
export function useCanGrantVerifier(): boolean {
  const { roles } = useAuth();
  return hasAnyRole(roles, GRANT_VERIFIER_ROLES);
}
