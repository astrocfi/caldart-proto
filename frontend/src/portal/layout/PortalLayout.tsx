/**
 * The portal chrome: a left rail on desktop, a hamburger drawer on
 * mobile, filtered by the signed-in user's roles.
 */
import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';
import { groupedNavItems } from '../nav';

export function PortalLayout() {
  const { user, roles, isAuthenticated } = useAuth();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Any navigation closes the mobile drawer.
  useEffect(() => setDrawerOpen(false), [location.pathname]);

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
                <Link to="/logout" className="button button--quiet button--small">
                  Sign out
                </Link>
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
            <p className="portal__rail-footer muted">
              <a href="/">Back to caldart.org</a>
            </p>
          </nav>
        ) : null}

        <main className="portal__main" id="portal-main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
