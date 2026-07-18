# Dashboard

The generated dashboard is served from `status.<domain>` and written to
`/data/index.html` during bootstrap. It is a dependency-free operational view,
not a replacement for full monitoring or certificate observability.

## Primary Workflows

### Overview

The first section summarizes:

- configured upstream count,
- latest successful HTTP reachability checks,
- latest successful TLS/HTTPS reachability checks,
- whether the built Caddy version appears current.

HTTP error responses still count as reachable because the target returned a
response. This distinguishes network reachability from application health.

### Services

- Filter by service name, public URL, or upstream target.
- Use **Run all checks** to refresh every service.
- Use per-service **Check ping** and **Check TLS** actions for focused retries.
- Open public endpoints in a new tab from the service table.

The browser checks the server-side `status.<domain>/probe/<service>/` routes.
They do not expose the peer certificate chain, cipher, or expiry details.
Responses below HTTP 500 count as reachable—even when authentication returns 401 or
a route returns 404—while HTTP 5xx responses count as failed service checks.

### Certificates

- The local snapshot comes from `/crtsh-state.json`.
- Server-side snapshot downloads are size-bounded, malformed rows are ignored,
  and at most 5,000 valid rows are persisted. Metadata retains the total valid-row
  count and reports whether storage was truncated.
- **Refresh live** queries crt.sh through `/probe/crtsh` to avoid browser CORS
  restrictions.
- Browser JSON reads are aborted when they exceed 8 MiB, including streamed
  responses without a trustworthy `Content-Length` header.
- Certificate history can be filtered client-side.
- At most 200 matching history rows are inserted into the DOM to keep large
  result sets responsive.

### ACME

The ACME section presents state, subjects, generation time, and the runtime note
as a definition list. Raw JSON remains available inside a collapsed disclosure
for diagnosis.

## Accessibility and Interaction

- Semantic `header`, `nav`, `main`, `section`, table, caption, and heading
  structure.
- A keyboard-visible skip link to the main dashboard content.
- Strong `:focus-visible` indicators and controls at least 44 px high.
- Native buttons, links, inputs, tables, and disclosure elements rather than
  custom ARIA widgets.
- Polite status regions for asynchronous operations and filter results.
- Responsive service records with visible field labels on narrow screens.
- System color-scheme detection plus persisted light and dark overrides.
- Reduced animation when `prefers-reduced-motion: reduce` is active.
- Stronger borders when `prefers-contrast: more` is active.

The theme control cycles through **system**, **light**, and **dark**. The chosen
override is stored in local browser storage when available.

## Keyboard Use

1. Press `Tab` after opening the page to reveal the skip link.
2. Use the section navigation links to move between dashboard areas.
3. Use standard `Tab`, `Shift+Tab`, `Enter`, and `Space` behavior for controls.
4. Type directly in either search field to filter its associated table.

## Operational Limitations

- Browser TLS checks are reachability probes, not full certificate inspection.
- crt.sh is an external service and may be unavailable or rate limited.
- The dashboard is currently unauthenticated unless protected by surrounding
  network or proxy policy; this remains tracked in `issues.yml`.
- The page deliberately has no frontend framework or external asset dependency,
  so it remains usable from the generated runtime directory.
