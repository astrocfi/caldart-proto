/**
 * The portal chrome: a left rail on desktop, a hamburger drawer on
 * mobile, filtered by the signed-in user's roles and, for Renew, their kind.
 *
 * A reader who has not finished the join wizard (`isOnboarded`) gets neither the
 * rail nor the **Menu** toggle: the wizard is the whole portal until it is done, so
 * the header keeps only **Help**, the address, and **Sign out**.
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';

import { useAuth, useSignOut } from '../auth/useAuth';
import { isOnboarded } from '../features/join/steps';
import { Button } from '../components/Button';
import { GUIDE_PREFIX } from '../guide';
import { helpPath } from '../help';
import { groupedNavItems } from '../nav';
import { sitePath } from '../urlPrefix';

/** The portal chrome: header, role-filtered navigation, and the routed page outlet. */
export function PortalLayout(): JSX.Element {
  const { user, roles, isAuthenticated } = useAuth();
  const { signOut, isPending: isSigningOut } = useSignOut();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Any navigation closes the mobile drawer and puts the page back at the top:
  // a screen opened from halfway down the last one starts mid-content
  // otherwise, because the browser keeps the scroll position of the document.
  useEffect(() => {
    setDrawerOpen(false);
    window.scrollTo({ top: 0, left: 0 });
  }, [location.pathname]);

  const isEffectiveFriend = user?.membership.status === 'friend';
  const groups = isOnboarded(user) ? groupedNavItems(roles, isEffectiveFriend) : [];
  const hasRail = groups.length > 0;

  return (
    <div className="portal" data-drawer-open={drawerOpen ? 'true' : 'false'}>
      <a className="skip-link" href="#portal-main">
        Skip to content
      </a>

      <header className="portal__bar">
        <div className="portal__bar-inner">
          {hasRail ? (
            <button
              type="button"
              className="button button--quiet button--small portal__drawer-toggle"
              aria-expanded={drawerOpen}
              aria-controls="portal-nav"
              onClick={() => setDrawerOpen((open) => !open)}
            >
              Menu
            </button>
          ) : null}

          <Link to="/" className="wordmark portal__wordmark">
            Cal<span>DART</span>
            <span className="wordmark__sub">Member portal</span>
          </Link>

          <div className="portal__identity">
            {/* A plain anchor, not `Link`: the guide is outside the SPA, under a
                path the router's basename would otherwise prefix onto. */}
            <a
              href={helpPath(location.pathname)}
              className="button button--quiet button--small portal__help-link"
              target="_blank"
              rel="noopener"
              aria-label="Help for this screen"
            >
              Help
            </a>
            {isAuthenticated && user ? (
              <>
                <span className="muted portal__email">{user.email}</span>
                <Button variant="quiet" small onClick={() => signOut()} disabled={isSigningOut}>
                  Sign out
                </Button>
              </>
            ) : (
              <Link to="/login" className="button button--small">
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>

      <div className={hasRail ? 'portal__frame' : 'portal__frame portal__frame--no-rail'}>
        {hasRail ? (
          <nav className="portal__rail" id="portal-nav" aria-label="Portal sections">
            {groups.map((bucket) => (
              <div key={bucket.group} className="portal__nav-group">
                <p className="eyebrow">{bucket.group}</p>
                <ul role="list">
                  {bucket.items.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        end={item.end}
                        className={({ isActive }) =>
                          isActive ? 'portal__nav-link is-active' : 'portal__nav-link'
                        }
                      >
                        {item.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            <div className="portal__rail-footer muted">
              <p>
                <a href={GUIDE_PREFIX} target="_blank" rel="noopener">
                  User guide
                </a>
              </p>
              <p>
                <a href={sitePath('/')}>Back to caldart.org</a>
              </p>
            </div>
          </nav>
        ) : null}

        <main className="portal__main" id="portal-main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
