#!/bin/bash
# Uptime Kuma Monitor Setup Script
#
# Usage:
#   1. Start Uptime Kuma and complete initial setup (create admin account)
#   2. Go to Settings → API Keys and create a new API key
#   3. Run: ./uptime-kuma-setup.sh YOUR_API_KEY

set -e

API_KEY="$1"
UPTIME_KUMA_URL="https://status.lundmark.tech"

if [ -z "$API_KEY" ]; then
    echo "Error: API key required"
    echo "Usage: $0 YOUR_API_KEY"
    exit 1
fi

# Function to create a monitor
create_monitor() {
    local name="$1"
    local url="$2"
    local group="$3"
    local interval="${4:-60}"

    echo "Creating monitor: $name"

    curl -X POST "$UPTIME_KUMA_URL/api/add-monitor" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $API_KEY" \
        -d @- << EOF
{
    "type": "http",
    "name": "$name",
    "url": "$url",
    "interval": $interval,
    "retryInterval": 60,
    "maxretries": 3,
    "notificationIDList": [],
    "ignoreTls": false,
    "upsideDown": false,
    "maxredirects": 10,
    "accepted_statuscodes": ["200-299"],
    "dns_resolve_type": "A",
    "dns_resolve_server": "1.1.1.1",
    "proxyId": null,
    "method": "GET",
    "body": null,
    "headers": null,
    "authMethod": null,
    "basic_auth_user": null,
    "basic_auth_pass": null,
    "timeout": 48,
    "keyword": null,
    "invertKeyword": false,
    "description": "$group"
}
EOF
    echo ""
    sleep 1
}

echo "Setting up Uptime Kuma monitors..."
echo ""

# System & Infrastructure (homeserver)
create_monitor "Traefik" "https://proxy.lundmark.tech/" "System & Infrastructure" 60
create_monitor "Uptime Kuma" "https://status.lundmark.tech/" "System & Infrastructure" 300
create_monitor "Portainer (homeserver)" "https://containers-server.lundmark.tech/" "System & Infrastructure" 120
create_monitor "AdGuard Home (DNS1)" "https://dns1.lundmark.tech/" "System & Infrastructure" 60
create_monitor "AdGuard Home Sync" "https://dns-sync.lundmark.tech/" "System & Infrastructure" 300

# System & Infrastructure (homecloud NAS)
create_monitor "Portainer (homecloud)" "https://containers-nas.lundmark.tech/" "System & Infrastructure" 120
create_monitor "AdGuard Home (DNS2)" "https://dns2.lundmark.tech/" "System & Infrastructure" 60

# System & Infrastructure (Synology)
create_monitor "Synology DSM" "https://dsm.lundmark.tech/" "System & Infrastructure" 120
create_monitor "Synology VMM" "https://vm.lundmark.tech/" "System & Infrastructure" 300

# System & Infrastructure (Network)
create_monitor "UniFi Controller" "https://network.lundmark.tech/" "System & Infrastructure" 120
create_monitor "APC UPS (Rack)" "https://ups1.lundmark.tech/" "System & Infrastructure" 120
create_monitor "APC UPS (Desktop)" "https://ups2.lundmark.tech/" "System & Infrastructure" 120

# Home & Security
create_monitor "Home Assistant" "https://home.lundmark.tech/" "Home & Security" 60
create_monitor "Homebridge" "https://homebridge.lundmark.tech/" "Home & Security" 120
create_monitor "Scrypted" "https://cameras.lundmark.tech/" "Home & Security" 120

# Storage & Backup
create_monitor "Synology File Station" "https://files.lundmark.tech/" "Storage & Backup" 300
create_monitor "Synology Drive" "https://drive.lundmark.tech/" "Storage & Backup" 300
create_monitor "Active Backup for Business" "https://backup.lundmark.tech/" "Storage & Backup" 300

# Photos & Memories
create_monitor "Immich" "https://photos.lundmark.tech/" "Photos & Memories" 120
create_monitor "iCloudPD" "https://icloudpd.lundmark.tech/" "Photos & Memories" 300
create_monitor "iCloudPD (Shared)" "https://icloudpd-shared.lundmark.tech/" "Photos & Memories" 300

# Media Library
create_monitor "Plex" "https://watch.lundmark.tech/" "Media Library" 60
create_monitor "Seerr" "https://requests.lundmark.tech/" "Media Library" 120
create_monitor "Tautulli" "https://stats.lundmark.tech/" "Media Library" 300

# Media Automation
create_monitor "Sonarr" "https://tv.lundmark.tech/" "Media Automation" 120
create_monitor "Radarr" "https://movies.lundmark.tech/" "Media Automation" 120
create_monitor "Lidarr" "https://music.lundmark.tech/" "Media Automation" 120
create_monitor "Bazarr" "https://subtitles.lundmark.tech/" "Media Automation" 300
create_monitor "HandBrake" "https://encoder.lundmark.tech/" "Media Automation" 300

# Downloads & Indexers
create_monitor "Transmission" "https://torrents.lundmark.tech/" "Downloads & Indexers" 120
create_monitor "SABnzbd" "https://usenet.lundmark.tech/" "Downloads & Indexers" 120
create_monitor "NZBHydra2" "https://search.lundmark.tech/" "Downloads & Indexers" 300
create_monitor "Prowlarr" "https://indexers.lundmark.tech/" "Downloads & Indexers" 120

echo ""
echo "✓ All monitors created successfully!"
echo ""
echo "Next steps:"
echo "1. Visit $UPTIME_KUMA_URL to view your monitors"
echo "2. Set up notification channels (Settings → Notifications)"
echo "3. Assign notifications to monitor groups or individual monitors"
