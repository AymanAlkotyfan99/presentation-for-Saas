# Deployment administrator bootstrap

The public `POST /api/v1/auth/setup` flow has been removed. This is an intentional
breaking security change: an unauthenticated visitor can no longer claim an
unconfigured instance.

For an authenticated server deployment, supply the initial administrator through
deployment-time secrets before the first startup:

```text
AUTH_USERNAME=<administrator username>
AUTH_PASSWORD=<secret supplied by the deployment secret store>
```

Do not put the password in Compose files, images, source control, or shell-history
examples. Use the platform's secret injection facility. Passwords must contain at
least eight characters and usernames at least three.

Startup fails closed when authentication is enabled and neither a database
administrator nor valid deployment credentials exist. The database transaction
serializes first-administrator provisioning, assigns the unique primary-admin
slot, migrates legacy ownership, and commits once. Concurrent replicas therefore
cannot create two initial administrators. Once an administrator exists, ordinary
startup credentials cannot create or replace another account.

`AUTH_OVERRIDE_FROM_ENV=true` and `RESET_AUTH=true` are explicit recovery or
rotation operations for the existing primary account. Each requires
`AUTH_PASSWORD`; they preserve the user ID, increment the authentication version,
and revoke existing API tokens. Remove the operation flag after the successful
startup.

`DISABLE_AUTH=true` permits startup without an administrator for the intentionally
local desktop/development mode. It must not be used for a publicly reachable web
deployment. Development convenience must use an isolated local environment and
must not restore the retired HTTP setup endpoint.

