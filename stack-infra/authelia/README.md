# Authelia Setup

## User Management

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
| Client Secret     | contents of `secrets/oidc_portainer_secret`          |
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

The client secrets (plain text) are stored in `secrets/oidc_portainer_secret` and `secrets/oidc_immich_secret`.

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

## Secrets

All secrets are in the `secrets/` directory (git-ignored):

| File                    | Purpose                                   |
| ----------------------- | ----------------------------------------- |
| `jwt`                   | JWT signing for password reset            |
| `session`               | Session encryption                        |
| `encryption`            | Storage encryption                        |
| `oidc_hmac`             | OIDC HMAC secret                          |
| `oidc_jwks.pem`         | OIDC JWT signing key (RSA 4096)           |
| `oidc_portainer_secret` | Portainer OIDC client secret (plain text) |
| `oidc_immich_secret`    | Immich OIDC client secret (plain text)    |
