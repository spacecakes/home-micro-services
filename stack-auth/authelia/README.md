# Authelia Setup

## User Management

`users_database.yml` is git-ignored because it holds password hashes and emails. The live copy is on the Docker LXC, and the PBS backups of that LXC cover it.

### Change your password

Generate a new hash:

```bash
docker run --rm authelia/authelia:latest authelia crypto hash generate argon2 --password 'NEW_PASSWORD'
```

Replace the `password` field in `users_database.yml` with the output. Restart Authelia:

```bash
cd /srv/docker/stack-infra && docker compose restart authelia
```

### Add a new user

Add an entry to `users_database.yml`:

```yaml
users:
  newuser:
    displayname: New User
    password: '$argon2id$...' # generate with the command above
    email: user@example.com
```

Restart Authelia to pick up the change.

## TOTP (Two-Factor)

1. Log in at `auth.lundmark.tech`
2. Register a TOTP device from the Authelia portal
3. Since we use the filesystem notifier, the registration link is written to a file:

```bash
docker exec authelia cat /data/notification.txt
```

Open the link to complete TOTP setup with your authenticator app.

## OIDC Clients

Authelia acts as an OIDC identity provider for services that support it.

### Portainer

Configure in the Portainer UI under Settings > Authentication > OAuth:

| Field             | Value                                               |
| ----------------- | --------------------------------------------------- |
| Provider          | Custom                                              |
| Client ID         | `portainer`                                         |
| Client Secret     | contents of `secrets/oidc_portainer_secret`         |
| Authorization URL | `https://auth.lundmark.tech/api/oidc/authorization` |
| Access token URL  | `https://auth.lundmark.tech/api/oidc/token`         |
| Resource URL      | `https://auth.lundmark.tech/api/oidc/userinfo`      |
| Redirect URL      | `https://containers.lundmark.tech`                  |
| User Identifier   | `preferred_username`                                |
| Scopes            | `openid profile email`                              |

Note: Portainer uses `client_secret_basic` (Authelia's default), so no extra config needed in `configuration.yml`. Do **not** put Portainer behind the `authelia@file` forward auth middleware — it conflicts with the OIDC callback redirect.

### Immich

Configure in the Immich admin UI under Administration > Settings > OAuth:

| Field         | Value                                    |
| ------------- | ---------------------------------------- |
| Issuer URL    | `https://auth.lundmark.tech`             |
| Client ID     | `immich`                                 |
| Client Secret | contents of `secrets/oidc_immich_secret` |
| Scope         | `openid profile email`                   |
| Button Text   | `Login with Authelia`                    |
| Auto Register | Enabled                                  |

Note: Immich uses `client_secret_post`, so the Authelia client config needs `token_endpoint_auth_method: client_secret_post`.

### Synology DSM

[Authelia guide](https://www.authelia.com/integration/openid-connect/clients/synology-dsm/)

Configure under Control Panel > Domain/LDAP > SSO Client > OAuth:

| DSM Field           | Value                                                         |
| ------------------- | ------------------------------------------------------------- |
| Profile             | OIDC                                                          |
| Account Type        | Domain/LDAP/local                                             |
| Name                | Authelia                                                      |
| Well Known URL      | `https://auth.lundmark.tech/.well-known/openid-configuration` |
| Application ID      | `synology-dsm`                                                |
| Application Key     | contents of `secrets/oidc_dsm_secret`                         |
| Redirect URL        | `https://dsm.lundmark.tech`                                   |
| Authorization Scope | `openid profile groups email`                                 |
| Username Claim      | `preferred_username`                                          |

Note: DSM uses `client_secret_post`. DSM does **not** auto-create users — the Authelia username (`preferred_username`) must match an existing DSM local/LDAP account. Do **not** put DSM behind the `authelia@file` forward auth middleware — it conflicts with the OIDC callback redirect.

### Proxmox Backup Server

Configure in the PBS web UI under Configuration > Access Control > Realms > Add > OpenID Connect:

| Field           | Value                                                         |
| --------------- | ------------------------------------------------------------- |
| Realm           | `authelia`                                                    |
| Issuer URL      | `https://auth.lundmark.tech`                                  |
| Client ID       | `pbs`                                                         |
| Client Key      | contents of `secrets/oidc_pbs_secret`                         |
| Autocreate User | Checked (or manually create matching users)                   |
| Username Claim  | `preferred_username`                                          |
| Scopes          | `openid profile email`                                        |

Note: PBS uses the same OIDC flow as Proxmox VE (`client_secret_basic` + PKCE). After adding the realm, users can log in by selecting the `authelia` realm on the PBS login page. You may need to grant permissions to the auto-created user (`user@authelia`) under Access Control > Permissions.

The client secrets (plain text) are stored in the `secrets/` directory (see Secrets table below).

## Adding a new OIDC client

1. Generate a secret:

```bash
SECRET=$(openssl rand -hex 32)
echo "$SECRET" > secrets/oidc_newclient_secret
docker run --rm authelia/authelia:latest authelia crypto hash generate pbkdf2 --password "$SECRET"
```

2. Add the client to `configuration.yml` under `identity_providers.oidc.clients`
3. Restart Authelia

## Forward Auth

For services without OIDC support, add this Traefik label to put them behind Authelia:

```yaml
- 'traefik.http.routers.<service>.middlewares=authelia@file'
```

No per-service config needed — the session cookie covers all `*.lundmark.tech`.

## Troubleshooting

### Dashboard loads without CSS / login forgotten on reload

The usual cause is a stale duplicate `authelia_session` cookie in the browser (e.g. one scoped to a subdomain plus one for `lundmark.tech`). The browser sends both, Authelia reads the stale one, and subresources (CSS, icons) come back as a 302 to the login page with `text/html`. Fix it by deleting all cookies for `lundmark.tech` and its subdomains, then logging in again.

To confirm it's this and not something else, check the Authelia logs for successful logins followed by anonymous requests from the same IP:

```bash
docker logs authelia --since 10m 2>&1 | grep -iE "anonymous|successful"
```

### Session count

Every request without a cookie that goes through forward-auth creates a Redis session that lives for `session.expiration` (30d). That includes requests matched by a `bypass` rule. A healthy count is in the low thousands at most, and it should only grow when real browsers visit:

```bash
docker exec authelia-redis redis-cli dbsize
```

If it keeps climbing, something is polling a protected URL without credentials, usually a monitor. Uptime Kuma must send basic auth as the `kuma` user (see the Kuma notes in CLAUDE.md). To find the culprit, look for repeated anonymous requests from a single IP:

```bash
docker logs authelia --since 10m 2>&1 | grep "username= " | grep -oE "ip=[0-9.]+ and object [^ ]+" | sort | uniq -c | sort -rn | head
```

Once it's fixed, flush with `docker exec authelia-redis redis-cli flushdb`. This logs everyone out.

### Service accounts

`kuma` is a password-only account for Uptime Kuma. It's limited to the NAS's IP by the `access_control` rule. Its password is stored only in Kuma's monitor settings. To rotate it, generate a new hash as above, update `users_database.yml`, and update the basic-auth password on every Kuma monitor that uses it. A daily cron job (`/etc/cron.d/authelia-prune-kuma` → `/usr/local/sbin/authelia-prune-kuma`) deletes kuma's successful logins older than 7 days, since Authelia records one for every check.

## Secrets

All secrets are in the `secrets/` directory (git-ignored):

| File                    | Purpose                                      |
| ----------------------- | -------------------------------------------- |
| `jwt`                   | JWT signing for password reset               |
| `session`               | Session encryption                           |
| `encryption`            | Storage encryption                           |
| `oidc_hmac`             | OIDC HMAC secret                             |
| `oidc_jwks.pem`         | OIDC JWT signing key (RSA 4096)              |
| `oidc_portainer_secret` | Portainer OIDC client secret (plain text)    |
| `oidc_immich_secret`    | Immich OIDC client secret (plain text)       |
| `oidc_dsm_secret`       | Synology DSM OIDC client secret (plain text) |
| `oidc_pbs_secret`       | PBS OIDC client secret (plain text)           |
