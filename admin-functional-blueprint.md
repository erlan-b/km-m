# Admin Functional Blueprint (Reference Behavior)

## Purpose

This document captures UX behavior and functional layout patterns from the neighboring admin project as reference.
It is intentionally limited to:

- button placement patterns,
- page composition,
- interaction flow,
- module behavior.

It must not be used to copy:

- visual design implementation,
- color system,
- code structure,
- component internals.

## Core Shell Pattern

1. Global guarded admin shell:
- role-gated access for admin pages,
- redirect/fallback states for unauthenticated and unauthorized users.

2. Layout structure:
- fixed left sidebar,
- main content area offset by sidebar width,
- optional page header block with title/description,
- consistent page paddings.

3. Sidebar behavior:
- vertical nav list with icons,
- active route highlighting,
- badge counters near moderation-heavy items,
- bottom utility block (language/profile/logout),
- mobile collapse + overlay.

## Page Composition Pattern (Reusable)

Each admin entity page follows this structure:

1. Optional "pending items" alert card:
- shows pending count,
- has a quick button to apply pending filter.

2. Search + filter strip:
- search input on the left,
- filter popover button on the right,
- search submit button aligned with filters,
- optional extra controls near filter button.

3. Main data table card:
- server-driven list,
- status chips,
- per-row action buttons,
- empty/loading/error states.

4. Pagination footer:
- previous/next controls,
- range summary.

5. Action modals:
- details modal,
- reject/resolve modal with note,
- delete confirmation modal.

## Interaction Pattern Details

1. Filter UX:
- filter button opens compact floating panel,
- panel has grouped sections (status, type, sort),
- active option is visually highlighted,
- click outside closes panel,
- filter changes reset page to 1.

2. Search UX:
- controlled input state,
- submit triggers backend query,
- clear input supported,
- query and filters are independent but coordinated.

3. Table actions:
- row actions are conditional by status/permissions,
- destructive actions require confirmation,
- action button loading shown per row,
- successful moderation updates pending counters immediately.

4. State persistence:
- list filter/sort/page state persisted per module (local storage key per page),
- page can restore last used moderation context.

## Dashboard Pattern

Dashboard has 3 blocks:

1. Top KPI cards:
- each card is clickable to jump to the relevant module.

2. Detailed statistics cards:
- grouped metrics by domain (users/items/etc.).

3. Quick action row:
- direct action buttons for pending moderation queues,
- one manual refresh action.

## Auth and Access Behavior

1. Protected route wrapper at layout level.
2. Role checks for admin/superadmin-sensitive items.
3. Unauthorized states shown as explicit pages/cards with next action button.
4. Login page is minimal and focused:
- email/password,
- inline error area,
- primary login CTA.

## Our Domain Mapping (km-m)

Apply this same UX pattern to required modules:

1. Dashboard
2. Users
3. Listings moderation
4. Reports queue
5. Categories
6. Payments
7. Promotions
8. Localization
9. Audit logs

## Our Implementation Rules

1. Keep the exact behavior patterns above, but implement with our own design tokens and components.
2. Do not copy source code or CSS from the reference project.
3. Keep backend contract as source of truth from km-m backend APIs.
4. Keep the approved palette and style direction from our admin plan.

## First Build Slice (Using This Blueprint)

1. Scaffold admin shell (sidebar + protected layout + content wrapper).
2. Build shared SearchBar/FilterPopover/DataTable primitives.
3. Implement Dashboard page with KPI cards + quick actions.
4. Implement Users and Reports pages using the shared page composition pattern.
