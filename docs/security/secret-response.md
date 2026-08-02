# Secret exposure response

Treat every credential committed to a snapshot, screenshot, trace, log, fixture,
or source file as compromised. Deleting the current file is necessary but does
not revoke the credential or remove it from existing clones and Git history.

## Local and CI scanning

Run the dependency-free repository scan from the repository root. It checks
tracked files and non-ignored files that could be added to the next commit:

```text
python scripts/scan_secrets.py
```

The scanner reports only a detector and file location; matched values are always
redacted. CI runs the same command for pull requests and pushes to `main`.

Generated Playwright snapshots, traces, reports, HAR files, videos, and test
results are ignored because they can capture session cookies, provider keys, and
private presentation content. If a deterministic credential is required by a
test, its value must contain an unmistakable marker such as `unit-test`,
`clearly-fake`, or `invalid` and it must never authenticate to a real service.

## Incident procedure

1. Stop sharing the affected artifact. Restrict access without copying the
   credential into an issue, chat message, ticket, or terminal transcript.
2. Identify the credential owner, provider, environment, scopes, and possible
   exposure window from redacted metadata only.
3. Revoke the exposed credential at the external provider. When immediate
   revocation would cause an outage, create a replacement first, deploy it from
   the approved secret store, verify it, and then revoke the old credential.
4. Remove the credential-bearing artifact from the current branch. Replace a
   necessary fixture with a clearly fake deterministic value and add an ignore
   rule or generation control that prevents recurrence.
5. Run `python scripts/scan_secrets.py`, the affected authentication tests, and
   the normal CI suite. Validate the replacement through the provider's safe
   identity or health endpoint; do not print either credential.
6. Review provider audit logs from the earliest possible exposure through
   revocation. Escalate unexpected source addresses, usage, privilege changes,
   billing changes, or newly created credentials through the security process.
7. Notify repository maintainers, the credential owner, security, and affected
   service owners. Communicate the credential type and incident status, never its
   value.

External-provider revocation and rotation require authorized human access. They
must remain explicitly **unverified/manual** until the provider owner confirms
completion. Removing a file in this repository does not complete those actions.

## Coordinated Git history cleanup

Do not rewrite shared history as part of an ordinary remediation pull request.
After revocation, repository administrators should schedule a maintenance window,
make a recoverable mirror backup, notify all collaborators, protect or pause
merges, and use an approved tool such as `git filter-repo` to remove the exact
affected path or value. Use placeholders in the cleanup command or replacement
file; never paste the credential into shell history.

After the force push, invalidate old pull-request refs where the hosting provider
supports it, ask collaborators to discard old clones and re-clone, rescan all
branches/tags, and verify the host no longer exposes the affected objects. Retain
only sanitized incident evidence under the organization's restricted retention
policy.
