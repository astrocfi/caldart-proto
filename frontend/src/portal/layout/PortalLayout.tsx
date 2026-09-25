/**
 * The portal chrome: a left rail on desktop, a hamburger drawer on
 * mobile, filtered by the signed-in user's roles.
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';

import { useAuth, useSignOut } from '../auth/useAuth';
import { Button } from '../components/Button';
import { guidePath } from '../guide';
import { groupedNavItems } from '../nav';

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

  const groups = isAuthenticated ? groupedNavItems(roles) : [];

  return (
    <div className="portal" data-drawer-open={drawerOpen ? 'true' : 'false'}>
      <a className="skip-link" href="#portal-main">
        Skip to content
      </a>

      <header className="portal__bar">
        <div className="portal__bar-inner">
          {isAuthenticated ? (
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

      <div className="portal__frame">
        {groups.length > 0 ? (
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
                <a href={guidePath(roles)}>User guide</a>
              </p>
              <p>
                <a href="/">Back to caldart.org</a>
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
