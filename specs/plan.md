# Release Manager public website expansion — implementation plan

## Objective and boundaries

Expand the existing public Next.js marketing surface into a complete, original Release Manager product site at `/`, `/about`, and `/contact`. The content will explain an evidence-based, human-governed GitHub release process and preserve the current bold editorial, restrained-neumorphic visual language without copying Teamwork's branding, wording, graphics, or visual concept.

This increment is frontend marketing work only. It will not add any public route other than `/about` and `/contact`, and it will not change `/login`, GitHub OAuth, `/dashboard`, backend APIs, database schemas, authentication/session semantics, scheduling, or release workflow behavior. No new runtime dependency, remote font, backend integration, form submission, external contact redirect, credential, or secret file is planned.

## Planned files, in implementation order

1. **Create `frontend/components/MarketingHeader.tsx`**
   - Build the shared public-site header with a home/brand link and coherent links to Product (`/`), About (`/about`), Contact (`/contact`), and the existing login destination (`/login`).
   - Use semantic, labelled navigation and ordinary links so the header remains usable without client-side JavaScript and by keyboard.

2. **Create `frontend/components/MarketingFooter.tsx`**
   - Build the shared footer used by all three marketing pages, repeating concise product identity and navigable links among `/`, `/about`, `/contact`, and `/login`.
   - Keep Shipyard/Herald wording factual and avoid unsupported links or availability claims.

3. **Create `frontend/components/MarketingShell.tsx`**
   - Compose the shared header, exactly one `main` landmark supplied with page content, and the shared footer.
   - Keep this shell isolated from the authenticated dashboard shell and from the existing login page so auth behavior and dashboard navigation are not affected.

4. **Modify `frontend/app/page.tsx`**
   - Replace the short hero with a complete landing page ordered as: shared navigation, hero, product explanation, five-stage workflow, benefits, Shipyard introduction, final call to action, and shared footer.
   - Explain that Release Manager scans a GitHub repository, drafts an evidence-backed release pack, holds it for named-human review, publishes only after governance, records activity for audit, and supports a governed rollback path.
   - Present the workflow explicitly and in order as **Scan, Draft, Review, Publish, Rollback**.
   - Retain two prominent CTA destinations: `/login` for opening/signing into the console and `/about` for learning more. Do not expose account, repository, operation, token, or release data on the public page.
   - Remove the need for session-dependent marketing copy/CTA selection; visiting `/` remains a public 200 response for signed-out and signed-in visitors and never redirects to the dashboard.

5. **Create `frontend/app/about/page.tsx`**
   - Add the first new public route using the shared marketing shell.
   - State unambiguously that Release Manager is built by Shipyard, describe Shipyard as Herald's product-building platform, and connect that origin to governed, reviewable delivery without inventing Shipyard features or availability.
   - Include navigation back to the product landing page and onward to Contact/Login through the shared navigation.

6. **Create `frontend/app/contact/page.tsx`**
   - Add the second and final new public route using the shared marketing shell.
   - Clearly display a visible **Coming soon** status and explain that contact capability is not yet available.
   - Provide navigation back to the Release Manager product site. Do not render a form, submission control, mail link presented as a working contact channel, or external redirect.

7. **Modify `frontend/app/globals.css`**
   - Add styles scoped to the marketing shell and its sections, workflow, benefit layout, status treatment, calls to action, header, and footer.
   - Continue using the existing serif display/sans UI system fonts, surface/shadow/radius tokens, and `--accent-gold` as the sole visible accent. Use one restrained elevation level at a time and inset treatment for nested emphasis.
   - Supply responsive layouts that do not overflow at narrow mobile widths, preserve readable line lengths, and adapt navigation/CTA/workflow layouts without hiding destinations.
   - Preserve visible `:focus-visible` treatment, semantic target sizing, WCAG 2.1 AA text contrast, and the existing dashboard/login styles. Scope new selectors rather than broadening generic rules that could regress authenticated screens.
   - Ensure any decorative transition or animation is nonessential and disabled under `prefers-reduced-motion: reduce`.

8. **Modify `frontend/e2e/marketing.spec.ts`**
   - Replace obsolete assertions tied to the old hero/session-specific CTA with coverage for the expanded public site.
   - Verify `/` responds successfully without a session; has one main landmark; contains the required landing-page progression and ordered five-stage workflow; exposes prominent links to `/login` and `/about`; shares header/footer navigation; and contains no authenticated account data.
   - Verify signed-in visitors still receive the public landing page rather than a redirect, without asserting changes to authentication behavior.
   - Verify `/about` and `/contact` are direct, successful public pages; both use coherent shared navigation; About contains the required Shipyard/Herald and governance statements; Contact shows “Coming soon,” has a route back to `/`, has no form, and does not redirect externally.
   - Exercise keyboard focus/navigation for the shared links and run a narrow viewport assertion for visible, non-overflowing navigation and core content.

9. **Modify `README.md`**
   - Update the public route documentation to list `/`, `/about`, and `/contact`, while retaining the existing `/login`, OAuth, dashboard, health, environment, persistence, and two-project deployment instructions unchanged in substance.
   - State that Contact is a non-functional Coming soon page so operators do not mistake it for an integration or support endpoint.

## Acceptance criteria

### Routes and content

- `GET /`, `GET /about`, and `GET /contact` render publicly with successful responses and no session requirement; exactly `/about` and `/contact` are added as public marketing routes.
- The landing page follows the requested progression: navigation, hero, product explanation, workflow, benefits, Shipyard introduction, final CTA, footer.
- Landing copy accurately describes an evidence-based, human-governed GitHub workflow and visibly presents Scan → Draft → Review → Publish → Rollback in that order.
- The landing page has prominent calls to action whose destinations are `/login` and `/about`.
- About says Release Manager is built by Shipyard, identifies Shipyard as Herald's product-building platform, and ties it to governed, reviewable delivery without unsupported claims.
- Contact visibly says “Coming soon,” stays on `/contact`, offers navigation back to the product site, and contains neither a working form nor an external contact redirect.
- The three marketing pages use the same coherent header/footer navigation and original Release Manager visual/content concepts.

### Accessibility and responsive behavior

- Each marketing page has semantic header/navigation, exactly one main landmark, a footer, logical heading hierarchy, descriptive link names, visible keyboard focus, and at least 24 × 24 CSS-pixel interactive targets.
- Text meets WCAG 2.1 AA contrast targets; small gold text is not used on a light surface unless the existing dark gold ink token provides sufficient contrast.
- Pages remain legible and free of horizontal page overflow at narrow mobile and desktop widths; navigation destinations remain reachable on mobile.
- Meaning does not depend on motion, color, or decorative graphics. Reduced-motion preference disables any new nonessential movement.

### Regression and quality gates

- `/login` continues to initiate the existing GitHub OAuth route and retain existing error handling; authenticated `/dashboard` routes and auth gates remain unchanged.
- Public pages never render repository, release, operation, audit, schedule, OAuth token, or other account-specific data.
- No backend, persistence, OAuth configuration, environment-variable contract, Vercel topology, package dependency, or locked manifest change is introduced.
- The implementation passes the existing full verification sequence:
  1. `.venv/bin/python -m pytest -q`
  2. `npm --prefix frontend test`
  3. `npm --prefix frontend run test:e2e`
  4. `npm --prefix frontend run build`
- Browser binaries remain operator-provisioned with `shipyard setup --browser-tests`; package scripts must not install browsers.
- Manual review checks `/`, `/about`, and `/contact` at mobile and desktop widths, keyboard traversal/focus visibility, reduced-motion emulation, and visual consistency with `.impeccable.md`.

## Deployment readiness

### Build and start commands

- Initialize dependencies with `./init.sh` when needed.
- Frontend production build: `npm --prefix frontend run build`.
- Frontend production start: `npm --prefix frontend run start` (port/host may be supplied by the operator/platform).
- Standalone backend start remains `PYTHONPATH=backend .venv/bin/uvicorn src.app:app --host 127.0.0.1 --port 8000`.
- Local frontend development remains `npm --prefix frontend run dev -- --hostname 127.0.0.1 --port 13000`.
- This plan does not deploy anything or add deployment scripts.

### Health and readiness behavior

- The frontend has no new health endpoint; readiness is a successful Next.js start plus successful rendering of `/`, with `/about` and `/contact` used as public route smoke checks.
- Backend readiness remains `GET /health`, which returns `{"status":"ok"}` only after required configuration and database initialization succeed.
- Marketing rendering must not depend on backend health, GitHub availability, or an authenticated session.

### Environment variable names

No new or renamed variables are required. Existing names remain:

- Frontend: `RELEASE_MANAGER_API_URL`, `CRON_SECRET`.
- Backend: `DATABASE_URL`, `POSTGRES_URL`, `RELEASE_MANAGER_WEB_URL`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_CALLBACK_URL`, `SESSION_SECRET`, `CRON_SECRET`, `MAX_CONCURRENT_SCANS`, `TOKEN_ENCRYPTION_KEY`, `SCHEDULER_INTERVAL_SECONDS`, `RELEASE_MANAGER_DB`.
- Legacy topology compatibility only: `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`.

`RELEASE_MANAGER_API_URL` remains server-only; no `NEXT_PUBLIC_` secret or backend URL will be introduced, and no values or credentials will be written to files.

### Persistence and runtime assumptions

- The new marketing pages are stateless Next.js pages and add no cookies, writes, forms, jobs, storage, database tables, migrations, or API calls.
- Existing backend persistence remains Postgres through `DATABASE_URL`/`POSTGRES_URL` in production, with SQLite as the documented local/CI fallback; this increment does not alter those assumptions.
- Existing OAuth sessions, scheduler behavior, release records, and authenticated runtime boundaries remain unchanged.

### Provider configuration and operator documentation

- Preserve the README-required Vercel topology: two separate Vercel projects with Root Directories `frontend` (Next.js) and `backend` (FastAPI).
- The frontend reaches the separate API only through the explicit server-only `RELEASE_MANAGER_API_URL`. Do not add or document a Next.js rewrite as a route to the unrelated Python function.
- Preserve the backend's native Vercel Python entrypoint/configuration, frontend Cron proxy configuration, Vercel environment settings, production Postgres configuration, and `CRON_SECRET` relationship as currently documented.
- Preserve the README-required GitHub OAuth App Homepage URL and Authorization callback URL operator configuration; this increment requires no provider-console changes.
- Update only the public-route/operator description in `README.md`; no Vercel or GitHub credentials are created, stored, or inferred.
