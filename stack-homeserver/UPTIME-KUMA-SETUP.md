# Uptime Kuma Monitor Setup Guide

## Initial Setup

1. Start the container:
   ```bash
   docker compose up -d uptime-kuma
   ```

2. Visit https://status.lundmark.tech and create your admin account

3. Configure monitors using one of the methods below

## Option 1: Use the Setup Script (Recommended)

After initial setup, create an API key in Uptime Kuma:
- Go to Settings → API Keys
- Create a new API key
- Run the setup script:
  ```bash
  chmod +x uptime-kuma-setup.sh
  ./uptime-kuma-setup.sh YOUR_API_KEY
  ```

**Note:** If the script fails (API endpoints may vary by version), use Option 2 below.

## Option 2: Manual Setup (Reference Guide)

### Monitor Settings
- **Heartbeat Interval**: Time between checks
  - Critical services (Traefik, DNS, Home Assistant, Plex): 60s
  - Important services (Portainer, *arr apps): 120s
  - Less critical services: 300s (5 min)
- **Retries**: 3
- **Retry Interval**: 60s

### Monitors to Create

#### System & Infrastructure (12 monitors)
| Name | URL | Interval | Location |
|------|-----|----------|----------|
| Traefik | https://proxy.lundmark.tech/ | 60s | homeserver |
| Uptime Kuma | https://status.lundmark.tech/ | 300s | homeserver |
| Portainer (homeserver) | https://containers-server.lundmark.tech/ | 120s | homeserver |
| Portainer (homecloud) | https://containers-nas.lundmark.tech/ | 120s | 10.0.1.2 |
| UniFi Controller | https://network.lundmark.tech/ | 120s | 10.0.1.1 |
| AdGuard Home (DNS1) | https://dns1.lundmark.tech/ | 60s | homeserver |
| AdGuard Home (DNS2) | https://dns2.lundmark.tech/ | 60s | 10.0.1.2 |
| AdGuard Home Sync | https://dns-sync.lundmark.tech/ | 300s | homeserver |
| Synology DSM | https://dsm.lundmark.tech/ | 120s | 10.0.1.2 |
| Synology VMM | https://vm.lundmark.tech/ | 300s | 10.0.1.2 |
| APC UPS (Rack) | https://ups1.lundmark.tech/ | 120s | 10.0.1.5 |
| APC UPS (Desktop) | https://ups2.lundmark.tech/ | 120s | 10.0.1.6 |

#### Home & Security (3 monitors)
| Name | URL | Interval |
|------|-----|----------|
| Home Assistant | https://home.lundmark.tech/ | 60s |
| Homebridge | https://homebridge.lundmark.tech/ | 120s |
| Scrypted | https://cameras.lundmark.tech/ | 120s |

#### Storage & Backup (3 monitors)
| Name | URL | Interval |
|------|-----|----------|
| Synology File Station | https://files.lundmark.tech/ | 300s |
| Synology Drive | https://drive.lundmark.tech/ | 300s |
| Active Backup for Business | https://backup.lundmark.tech/ | 300s |

#### Photos & Memories (3 monitors)
| Name | URL | Interval |
|------|-----|----------|
| Immich | https://photos.lundmark.tech/ | 120s |
| iCloudPD | https://icloudpd.lundmark.tech/ | 300s |
| iCloudPD (Shared) | https://icloudpd-shared.lundmark.tech/ | 300s |

#### Media Library (3 monitors)
| Name | URL | Interval |
|------|-----|----------|
| Plex | https://watch.lundmark.tech/ | 60s |
| Seerr | https://requests.lundmark.tech/ | 120s |
| Tautulli | https://stats.lundmark.tech/ | 300s |

#### Media Automation (5 monitors)
| Name | URL | Interval |
|------|-----|----------|
| Sonarr | https://tv.lundmark.tech/ | 120s |
| Radarr | https://movies.lundmark.tech/ | 120s |
| Lidarr | https://music.lundmark.tech/ | 120s |
| Bazarr | https://subtitles.lundmark.tech/ | 300s |
| HandBrake | https://encoder.lundmark.tech/ | 300s |

#### Downloads & Indexers (4 monitors)
| Name | URL | Interval |
|------|-----|----------|
| Transmission | https://torrents.lundmark.tech/ | 120s |
| SABnzbd | https://usenet.lundmark.tech/ | 120s |
| NZBHydra2 | https://search.lundmark.tech/ | 300s |
| Prowlarr | https://indexers.lundmark.tech/ | 120s |

## Post-Setup Configuration

### 1. Group Monitors
Create groups matching your homepage categories:
- System & Infrastructure
- Home & Security
- Storage & Backup
- Photos & Memories
- Media Library
- Media Automation
- Downloads & Indexers

Assign each monitor to its appropriate group.

### 2. Set Up Notifications
Go to Settings → Notifications and configure your preferred notification channels:
- Email
- Discord
- Slack
- Telegram
- Pushover
- etc.

### 3. Assign Notifications to Monitors
- Critical services: Immediate notifications
- Important services: Notify after 2-3 failures
- Less critical: Daily summary or notify after 5+ failures

### 4. Status Page (Optional)
Create a public or private status page:
- Settings → Status Pages
- Add your monitors
- Customize appearance
- Share with family/friends if desired

## Tips

- Use the **Description** field to note which physical server/device hosts each service
- Enable **Certificate Expiry Notification** for internet-facing services (Plex, Home Assistant)
- Set up **Maintenance Windows** before planned updates
- Export backups regularly: Settings → Backup
