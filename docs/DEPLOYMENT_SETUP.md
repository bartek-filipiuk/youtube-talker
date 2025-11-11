# Production Deployment Setup Guide

This guide shows how to configure passwordless sudo for GitHub Actions deployments.

## Problem

GitHub Actions deployment fails with:
```
sudo systemctl daemon-reload
sudo: a password is required
Error: Process completed with exit code 1
```

## Solution: Configure Passwordless Sudo on Production Server

### Step 1: SSH to Your Production Server

```bash
ssh YOUR_USER@YOUR_SERVER
```

### Step 2: Find Your Deployment User

Check which user GitHub Actions uses to deploy:
```bash
whoami
```

This is usually the user in your `SERVER_USER` GitHub secret (e.g., `ubuntu`, `deploy`, `ec2-user`).

### Step 3: Create Sudoers Configuration File

**Important:** Use `visudo` to safely edit sudoers files.

```bash
# Create the file
sudo visudo -f /etc/sudoers.d/youtubetalker-deploy
```

**Paste this content** (replace `YOUR_DEPLOY_USER` with your actual username):

```sudoers
# YoutubeTalker Deployment - Passwordless Sudo Configuration

# Command alias for YoutubeTalker systemctl operations
Cmnd_Alias YOUTUBETALKER_SVC = \
    /bin/systemctl daemon-reload, \
    /bin/systemctl start youtubetalker-backend, \
    /bin/systemctl stop youtubetalker-backend, \
    /bin/systemctl restart youtubetalker-backend, \
    /bin/systemctl enable youtubetalker-backend, \
    /bin/systemctl disable youtubetalker-backend, \
    /bin/systemctl status youtubetalker-backend, \
    /bin/systemctl start youtubetalker-frontend, \
    /bin/systemctl stop youtubetalker-frontend, \
    /bin/systemctl restart youtubetalker-frontend, \
    /bin/systemctl enable youtubetalker-frontend, \
    /bin/systemctl disable youtubetalker-frontend, \
    /bin/systemctl status youtubetalker-frontend

# Grant passwordless sudo for deployment user
YOUR_DEPLOY_USER ALL=(ALL) NOPASSWD: YOUTUBETALKER_SVC
```

**Example for ubuntu user:**
```sudoers
ubuntu ALL=(ALL) NOPASSWD: YOUTUBETALKER_SVC
```

**Example for deploy user:**
```sudoers
deploy ALL=(ALL) NOPASSWD: YOUTUBETALKER_SVC
```

### Step 4: Save and Validate

1. **Save:** `Ctrl+O`, then `Enter`, then `Ctrl+X`
2. **Validate syntax:**
   ```bash
   sudo visudo -cf /etc/sudoers.d/youtubetalker-deploy
   ```

   ✅ You should see: `parsed OK`

   ❌ If you see errors, go back and fix the syntax

### Step 5: Set Correct Permissions

```bash
sudo chmod 0440 /etc/sudoers.d/youtubetalker-deploy
```

### Step 6: Test Passwordless Sudo

Test each command without password:

```bash
# Test daemon-reload
sudo -n systemctl daemon-reload
echo "✅ daemon-reload works" || echo "❌ daemon-reload failed"

# Test backend start
sudo -n systemctl start youtubetalker-backend
echo "✅ backend start works" || echo "❌ backend start failed"

# Test backend stop
sudo -n systemctl stop youtubetalker-backend
echo "✅ backend stop works" || echo "❌ backend stop failed"

# Test frontend start
sudo -n systemctl start youtubetalker-frontend
echo "✅ frontend start works" || echo "❌ frontend start failed"
```

**If all tests pass ✅**, passwordless sudo is configured correctly!

### Step 7: Verify Full Deployment Path

Find the **exact path** to systemctl on your server:

```bash
which systemctl
```

**Output should be:** `/bin/systemctl` or `/usr/bin/systemctl`

**If it's `/usr/bin/systemctl`**, update the sudoers file:

```bash
sudo visudo -f /etc/sudoers.d/youtubetalker-deploy
```

Change all `/bin/systemctl` to `/usr/bin/systemctl`:

```sudoers
Cmnd_Alias YOUTUBETALKER_SVC = \
    /usr/bin/systemctl daemon-reload, \
    /usr/bin/systemctl start youtubetalker-backend, \
    # ... etc
```

## Security Notes

✅ **This configuration is secure because:**
- Only grants access to **specific systemctl commands**
- Does **NOT** grant blanket `sudo` access
- Follows the **principle of least privilege**
- Only allows operations on YoutubeTalker services

❌ **Do NOT use:**
```sudoers
# DANGEROUS - DO NOT USE!
deploy ALL=(ALL) NOPASSWD: ALL
```

## Troubleshooting

### Error: "sudo: no tty present and no askpass program specified"

**Cause:** Command not in sudoers file or path doesn't match exactly.

**Fix:** Run `which systemctl` and ensure the path in sudoers matches exactly.

### Error: "parsed OK" but sudo still asks for password

**Cause:** Username doesn't match or file has wrong permissions.

**Fix:**
```bash
# Check username
whoami

# Fix permissions
sudo chmod 0440 /etc/sudoers.d/youtubetalker-deploy

# Verify file content
sudo cat /etc/sudoers.d/youtubetalker-deploy
```

### Deployment still failing

**Check GitHub Actions logs:**
1. Go to your repository → Actions
2. Click on the failed deployment
3. Look for the exact sudo command that's failing
4. Ensure that exact command is in your sudoers file

**Example:** If logs show:
```
sudo /usr/bin/systemctl daemon-reload
```

But your sudoers has:
```
/bin/systemctl daemon-reload
```

They **don't match!** Update sudoers to use `/usr/bin/systemctl`.

## After Configuration

Once passwordless sudo is configured:

1. **Merge PR #63** (Python cache clearing fix)
2. **Automatic deployment will trigger**
3. **Deployment should succeed** without password errors
4. **Verify:** Check GitHub Actions logs for "✅ Systemd daemon reloaded"

## Additional Commands You Might Need

If you need to restart services manually during deployment troubleshooting:

```bash
# Restart backend
sudo systemctl restart youtubetalker-backend

# Check status
sudo systemctl status youtubetalker-backend

# View logs
sudo journalctl -u youtubetalker-backend -n 50
```

All these commands are included in the passwordless sudo configuration.
