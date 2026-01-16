# AI Agent Notes: Mailu Mail Server for lgucalapan.ph

> **Purpose:** This document captures all configuration, issues, and solutions for the Mailu mail server deployment. Any AI agent working on this project should read this file first.

---

## Project Overview

| Property | Value |
|----------|-------|
| **Domain** | lgucalapan.ph |
| **Mail Hostname** | mail.lgucalapan.ph |
| **Server IP** | 72.60.43.21 |
| **Hosting Provider** | Hostinger |
| **DNS Provider** | Cloudflare |
| **Mailu Version** | 2024.06 |
| **Deployment Platform** | Dokploy |
| **Docker Compose Path** | /etc/dokploy/compose/mail-server-app-cpkd3a/code/prod/docker-compose.yml |
| **Data Root** | /mailu |

---

## Container Names

All containers use prefix `mail-server-app-cpkd3a-`:

| Service | Container Name |
|---------|----------------|
| Admin | mail-server-app-cpkd3a-admin-1 |
| Webmail | mail-server-app-cpkd3a-webmail-1 |
| Antispam (rspamd) | mail-server-app-cpkd3a-antispam-1 |
| Front (nginx) | mail-server-app-cpkd3a-front-1 |
| IMAP (dovecot) | mail-server-app-cpkd3a-imap-1 |
| SMTP (postfix) | mail-server-app-cpkd3a-smtp-1 |
| Redis | mail-server-app-cpkd3a-redis-1 |
| Resolver | mail-server-app-cpkd3a-resolver-1 |

---

## DNS Configuration (Cloudflare)

| Type | Name | Value | Notes |
|------|------|-------|-------|
| A | mail | 72.60.43.21 | Mail server |
| MX | @ | mail.lgucalapan.ph (priority 10) | Mail exchanger |
| TXT | @ | `v=spf1 mx ~all` | SPF record |
| TXT | _dmarc | `v=DMARC1; p=quarantine; rua=mailto:admin@lgucalapan.ph` | DMARC policy |
| TXT | mailu._domainkey | `v=DKIM1; k=rsa; p=MIIBIjAN...DAQAB` | DKIM public key (full key required) |

### PTR Record (Hostinger)
- IP: 72.60.43.21 → mail.lgucalapan.ph
- Must be set by hosting provider, not DNS provider

---

## Custom Modifications

### 1. Password Policy (Relaxed)

**File:** `/core/admin/mailu/utils.py`  
**Location in container:** `/app/mailu/utils.py`  
**Mount:** Read-only via docker-compose volume

**Changes:**
- Minimum password length: 8 → 5 characters
- Pwned password check: Disabled

**Code Change (around line 80-90):**
```python
# Original:
# if len(password) < 8:
# Changed to:
if len(password) < 5:

# Original pwned check - commented out or returns True always
```

### 2. Webmail Password Change Feature

**File:** `/webmails/roundcube/login/mailu.php`  
**Location in container:** `/var/www/roundcube/plugins/mailu/mailu.php`  
**Mount:** Entire login folder mounted to `/var/www/roundcube/plugins/mailu:ro`

**Issue:** Password change menu not appearing in Roundcube settings  
**Root Cause:** `init()` function checked `$rcmail->task == 'settings'` before registering hooks, but task variable isn't set during plugin initialization phase

**Solution:** Remove task check, register hooks unconditionally:

```php
// Original (broken):
$rcmail = rcmail::get_instance();
if ($rcmail->task == 'settings' && $rcmail->config->get('show_password_button', true)) {
    $this->add_hook('settings_actions', ...);
}

// Fixed:
$this->add_hook('settings_actions', array($this, 'settings_actions'));
$this->register_action('plugin.mailu-password', array($this, 'password_form'));
$this->register_action('plugin.mailu-password-save', array($this, 'password_save'));
```

### 3. Admin Button Hidden in Webmail

**File:** `/webmails/roundcube/config/config.inc.php`  
**Setting:** `$config['show_mailu_button'] = false;`

### 4. Footer Attribution Removed

**Files:**
- `/core/admin/mailu/ui/templates/base.html`
- `/core/admin/mailu/sso/templates/base_sso.html`

**Change:** Removed Flask/AdminLTE/GitHub attribution links from footer

### 5. Force IPv4 for SMTP

**File:** `/mailu/overrides/postfix/postfix.cf`  
**Location in container:** `/etc/postfix/main.cf` (appended)  
**Mount:** Maps to `/overrides` in smtp container

**Change:** Force Postfix to use IPv4 only to avoid IPv6 PTR/SPF failures.
```
inet_protocols = ipv4
```

---

## DKIM Configuration

### Key Files on Server

| Path | Purpose |
|------|---------|
| /mailu/dkim/lgucalapan.ph.mailu.key | Private key (permissions: 644) |
| /mailu/dkim/lgucalapan.ph.mailu.pub | Public key |

### Filename Format
Pattern: `{domain}.{selector}.key`  
Example: `lgucalapan.ph.mailu.key` (selector = mailu)

### Environment Variable
In `/prod/.env`:
```
DKIM_SELECTOR=mailu
```

### Rspamd DKIM Signing Override

**File:** `/mailu/overrides/rspamd/dkim_signing.conf`  
**Mount:** Maps to `/etc/rspamd/override.d/` in antispam container

**Content:**
```
sign_authenticated = true;
sign_local = true;
```

**Why needed:** Default rspamd skips DKIM signing for authenticated users and local networks. These settings force signing for all outgoing mail.

### Verify DKIM Vault Endpoint
```bash
docker exec mail-server-app-cpkd3a-antispam-1 wget -qO- 'http://admin:8080/internal/rspamd/vault/v1/dkim/lgucalapan.ph'
```

**Expected response:** JSON with selectors array containing domain, key, and selector  
**Empty response `{"data":{"selectors":[]}}` means:** Key file not found, wrong filename, or wrong permissions

---

## Common Issues & Solutions

### Issue 1: Emails Going to Spam

**Diagnostic Steps:**
1. Check email headers for SPF, DKIM, DMARC results
2. Verify DNS records: `dig +short TXT lgucalapan.ph`, `dig +short TXT mailu._domainkey.lgucalapan.ph`
3. Check PTR record: `dig +short -x 72.60.43.21`

**Common Causes:**
- Missing DKIM signature → Check rspamd override config
- DKIM=neutral (invalid public key) → DNS key truncated, update with full key
- PTR mismatch → Contact hosting provider

### Issue 2: DKIM Not Signing

**Check effective rspamd config:**
```bash
docker exec mail-server-app-cpkd3a-antispam-1 rspamadm configdump dkim_signing
```

**Verify sign_authenticated and sign_local are true**

### Issue 3: Webmail Mount Empty

**Symptom:** Files exist on host but container shows empty directory  
**Solution:** Recreate container (not just restart):
```bash
cd /etc/dokploy/compose/mail-server-app-cpkd3a/code/prod
docker compose -p mail-server-app-cpkd3a up -d webmail --force-recreate
```

### Issue 4: Config Changes Not Applied

**For rspamd:** Edits inside container are lost on restart. Use `/mailu/overrides/rspamd/` for persistent changes.

**For webmail plugin:** Must recreate container after file changes:
```bash
docker compose -p mail-server-app-cpkd3a up -d webmail --force-recreate
```

---

## Useful Commands

### Check DNS Records
```bash
ssh root@72.60.43.21 "dig +short TXT lgucalapan.ph"                    # SPF
ssh root@72.60.43.21 "dig +short TXT _dmarc.lgucalapan.ph"             # DMARC
ssh root@72.60.43.21 "dig +short TXT mailu._domainkey.lgucalapan.ph"   # DKIM
ssh root@72.60.43.21 "dig +short MX lgucalapan.ph"                     # MX
ssh root@72.60.43.21 "dig +short -x 72.60.43.21"                       # PTR
```

### Container Management
```bash
# Recreate specific service
cd /etc/dokploy/compose/mail-server-app-cpkd3a/code/prod
docker compose -p mail-server-app-cpkd3a up -d <service> --force-recreate

# View logs
docker logs mail-server-app-cpkd3a-<service>-1

# Execute command in container
docker exec mail-server-app-cpkd3a-<service>-1 <command>
```

### Check DKIM Signing Status
```bash
# Test vault endpoint
docker exec mail-server-app-cpkd3a-antispam-1 wget -qO- 'http://admin:8080/internal/rspamd/vault/v1/dkim/lgucalapan.ph'

# Check rspamd effective config
docker exec mail-server-app-cpkd3a-antispam-1 rspamadm configdump dkim_signing

# Check rspamd logs for DKIM
docker logs mail-server-app-cpkd3a-antispam-1 2>&1 | grep -i dkim
```

### Generate New DKIM Key (if needed)
```bash
# Generate key pair
openssl genrsa -out /mailu/dkim/lgucalapan.ph.mailu.key 2048
openssl rsa -in /mailu/dkim/lgucalapan.ph.mailu.key -pubout -out /mailu/dkim/lgucalapan.ph.mailu.pub

# Set permissions
chmod 644 /mailu/dkim/lgucalapan.ph.mailu.key
chown 999:999 /mailu/dkim/lgucalapan.ph.mailu.*

# Extract public key for DNS
cat /mailu/dkim/lgucalapan.ph.mailu.pub | grep -v '^---' | tr -d '\n'
```

---

## Volume Mounts (docker-compose.yml)

### Admin Container
```yaml
volumes:
  - ../core/admin/mailu/utils.py:/app/mailu/utils.py:ro
  - ../core/admin/mailu/ui/templates/base.html:/app/mailu/ui/templates/base.html:ro
  - ../core/admin/mailu/sso/templates/base_sso.html:/app/mailu/sso/templates/base_sso.html:ro
```

### Webmail Container
```yaml
volumes:
  - $ROOT/webmail:/data
  - ../webmails/roundcube/login:/var/www/roundcube/plugins/mailu:ro
  - ../webmails/roundcube/config/config.inc.php:/conf/config.inc.php:ro
  - ../Calapan_City_Logo.png:/var/www/roundcube/skins/elastic/images/calapan-logo.png:ro
```

### Antispam Container
```yaml
volumes:
  - $ROOT/filter:/var/lib/rspamd
  - $ROOT/dkim:/dkim:ro
  - $ROOT/overrides/rspamd:/etc/rspamd/override.d:ro
```

---

## Access URLs

| Service | URL |
|---------|-----|
| Admin Panel | https://mail.lgucalapan.ph/admin |
| Webmail | https://mail.lgucalapan.ph/webmail |

---

## Final Status (as of January 15, 2026)

| Check | Status |
|-------|--------|
| SPF | ✅ PASS |
| DKIM | ✅ PASS |
| DMARC | ✅ PASS |
| PTR | ✅ Correct |
| Password Change Feature | ✅ Working |
| Relaxed Password Policy | ✅ Working |
| Admin Button Hidden | ✅ Working |
| Footer Removed | ✅ Working |

---

## Troubleshooting Checklist

When debugging email delivery issues:

1. [ ] Check email headers for SPF/DKIM/DMARC results
2. [ ] Verify DNS records are correct and complete
3. [ ] Check DKIM key file exists with correct name pattern
4. [ ] Verify DKIM key file has correct permissions (644)
5. [ ] Confirm DKIM_SELECTOR in .env matches key filename
6. [ ] Check rspamd override has sign_authenticated=true
7. [ ] Verify vault endpoint returns key (not empty selectors)
8. [ ] Restart/recreate containers after config changes
9. [ ] Compare DNS public key with server public key (must match exactly)
10. [ ] Verify PTR record with hosting provider
