# Authentication baseline

LunarForge Web uses Supabase Auth through `@supabase/ssr`. `/sandbox` requires a
verified session. `/admin` additionally requires a server-controlled admin role
and an Authenticator Assurance Level of `aal2`, produced by a verified TOTP
factor. Public product, documentation, login, and policy routes do not require a
session.

This phase does not add FastAPI, issue invitations from the web app, or store
application roles in client-editable Supabase user metadata.

## Environment

Copy `.env.example` to `.env.local` and set:

- `NEXT_PUBLIC_SUPABASE_URL`: the Supabase project URL.
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`: the browser-safe publishable key.
- `LUNAR_FORGE_ADMIN_USER_IDS`: comma-separated Supabase Auth UUIDs allowed to
  enter `/admin` after MFA.
- `LUNAR_FORGE_SUSPENDED_USER_IDS`: optional comma-separated UUIDs denied from
  protected routes.

The admin and suspension lists are an intentionally small, server-only bridge
until the later FastAPI/Neon authorization store exists. The frontend never
uses `user_metadata` as role authority. Never add a Supabase secret or
service-role key to `NEXT_PUBLIC_*`; this app does not need either credential in
this phase.

## Supabase project setup

1. Set the Auth Site URL to the deployed application origin. Add local and
   deployed `/auth/callback` URLs to the redirect allowlist.
2. Disable public self-registration for the private deployment. This app has no
   sign-up form or `signUp` call.
3. Invite ordinary users individually from the Supabase dashboard. Configure
   the invite email link to use:

   ```text
   {{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=invite
   ```

4. Configure the recovery email link to use:

   ```text
   {{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=recovery
   ```

5. Create or invite the permanent owner account, set its password, and put its
   Auth UUID in `LUNAR_FORGE_ADMIN_USER_IDS`. On first admin access, the app
   enrolls a TOTP authenticator. Later devices use the same account password and
   registered factor; they do not require another invitation.
6. Review Supabase password, email-delivery, invitation-expiry, session, and MFA
   settings for the deployment. Test both invite and recovery templates before
   inviting real users.

Invitation management belongs in the Supabase dashboard in this phase. A later
authenticated backend will provide owner controls without exposing elevated
Supabase credentials to the browser.

## Route enforcement

`src/middleware.ts` refreshes Supabase cookies and applies early redirects. The
protected route layouts independently call server helpers that verify claims,
so middleware is not the sole authorization boundary. Identity is derived with
`auth.getClaims()`; `auth.getSession()` is used only by the future API-token
helper after claims verification to retrieve the bearer token.

| Request | Result |
| --- | --- |
| Anonymous `/sandbox` | `/login?next=/sandbox` |
| Authenticated invited user `/sandbox` | Allowed |
| Ordinary user `/admin` | `/sandbox?error=admin_required` |
| Admin at `aal1` `/admin` | `/auth/mfa?next=/admin` |
| Admin at `aal2` `/admin` | Allowed |
| Suspended UUID on either protected surface | Login with suspension notice |

## Deterministic auth smoke tests

Playwright starts Next.js with `LUNAR_FORGE_AUTH_E2E_MODE=playwright` and uses a
dedicated test cookie to exercise anonymous, user, admin-`aal1`, admin-`aal2`,
and logout states without a live Supabase project. The bypass is accepted only
when `NODE_ENV` is not `production`; production builds cannot enable it. It is
not a deployment authentication mode.
