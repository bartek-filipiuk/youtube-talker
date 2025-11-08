# GitHub Secrets Setup Guide

This guide explains how to configure GitHub repository secrets for automated deployment.

## Overview

GitHub Secrets are encrypted environment variables that you create in a GitHub repository. They're used by GitHub Actions workflows to securely access sensitive information like SSH keys and server credentials.

## Required Secrets

You need to configure the following secrets for the deployment workflow to work:

### 1. SSH_PRIVATE_KEY

**Purpose:** SSH private key for authenticating with your production server

**How to get it:**

On your Digital Ocean droplet, generate an SSH key pair:

```bash
# SSH into your server
ssh root@YOUR_SERVER_IP

# Generate SSH key (if not already done)
ssh-keygen -t ed25519 -C "github-actions-deploy"

# Display the private key
cat ~/.ssh/id_ed25519
```

**Copy the entire output**, including the `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----` lines.

**Add to GitHub:**
1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `SSH_PRIVATE_KEY`
5. Value: Paste the entire private key
6. Click **Add secret**

⚠️ **Important:** Also add the corresponding public key to your server's `~/.ssh/authorized_keys`:

```bash
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 2. SERVER_HOST

**Purpose:** The IP address or hostname of your Digital Ocean droplet

**How to get it:**

From your Digital Ocean dashboard:
1. Go to Droplets
2. Copy your droplet's IP address

**Example:** `143.198.123.45` or `yourdomain.com`

**Add to GitHub:**
1. Repository → Settings → Secrets and variables → Actions
2. Click **New repository secret**
3. Name: `SERVER_HOST`
4. Value: Your server IP address
5. Click **Add secret**

### 3. SERVER_USER

**Purpose:** The username to use for SSH connection

**Recommended values:**
- `root` (if using root user)
- `deploy` (if you created a dedicated deploy user - recommended)

**Add to GitHub:**
1. Repository → Settings → Secrets and variables → Actions
2. Click **New repository secret**
3. Name: `SERVER_USER`
4. Value: `deploy` or `root`
5. Click **Add secret**

### 4. SERVER_DEPLOY_PATH

**Purpose:** The absolute path to your application directory on the server

**Recommended value:** `/opt/youtubetalker`

**Add to GitHub:**
1. Repository → Settings → Secrets and variables → Actions
2. Click **New repository secret**
3. Name: `SERVER_DEPLOY_PATH`
4. Value: `/opt/youtubetalker`
5. Click **Add secret**

## Optional Secrets

### CODECOV_TOKEN

**Purpose:** Token for uploading test coverage reports to Codecov

**How to get it:**
1. Sign up at [codecov.io](https://codecov.io)
2. Connect your GitHub repository
3. Copy the upload token

**Add to GitHub:**
1. Repository → Settings → Secrets and variables → Actions
2. Click **New repository secret**
3. Name: `CODECOV_TOKEN`
4. Value: Your Codecov token
5. Click **Add secret**

## Verification

After adding all secrets, verify they're configured correctly:

1. Go to: Repository → Settings → Secrets and variables → Actions
2. You should see:
   - `SSH_PRIVATE_KEY`
   - `SERVER_HOST`
   - `SERVER_USER`
   - `SERVER_DEPLOY_PATH`
   - `CODECOV_TOKEN` (optional)

## Testing the Setup

### Test SSH Connection Manually

Before pushing code, test that GitHub Actions can connect to your server:

```bash
# On your local machine, test SSH connection
ssh -i ~/.ssh/id_ed25519 deploy@YOUR_SERVER_IP "echo 'Connection successful!'"
```

If this works, GitHub Actions should be able to connect too.

### Test Deployment Workflow

1. Create a small change in a new branch
2. Push to GitHub and create a Pull Request
3. Watch the test workflow run
4. If tests pass, merge the PR
5. Watch the deploy workflow run
6. Check deployment logs in GitHub Actions

## Troubleshooting

### "Load key: error in libcrypto" Error

**Problem:** SSH key format is incorrect or corrupted

**This is the most common error when setting up SSH_PRIVATE_KEY secret.**

**Solutions:**

1. **Verify you copied the ENTIRE private key:**
   ```
   -----BEGIN OPENSSH PRIVATE KEY-----
   b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
   QyNTUxOQAAACDm8tPp+FJ0UXiG9kz8M9gEoYz...
   ... (many more lines) ...
   -----END OPENSSH PRIVATE KEY-----
   ```

   **Must include both BEGIN and END lines!**

2. **Get the key correctly:**
   ```bash
   # On your Digital Ocean droplet
   cat ~/.ssh/id_ed25519
   ```

   Copy the **entire output** - select from the very first character to the very last.

3. **Check for common mistakes:**
   - ❌ Copied public key (`.pub` file) instead of private key
   - ❌ Missing the `-----BEGIN` or `-----END` lines
   - ❌ Extra spaces or line breaks added when copying
   - ❌ Used wrong key type (use ed25519 or RSA, not DSA)
   - ❌ Key has Windows line endings (CRLF instead of LF)

4. **Test the key format locally:**
   ```bash
   # Create a test file with your key
   echo "YOUR_KEY_CONTENT" > test_key
   chmod 600 test_key

   # Try to use it (should not show libcrypto error)
   ssh -i test_key -o StrictHostKeyChecking=no YOUR_USER@YOUR_SERVER "echo test"
   ```

5. **Generate a new key if needed:**
   ```bash
   # On your server
   ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy

   # Add public key to authorized_keys
   cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys

   # Display private key to copy
   cat ~/.ssh/github_deploy
   ```

### "Permission denied (publickey)" Error

**Problem:** GitHub Actions can't authenticate with your server

**Solutions:**
1. Verify `SSH_PRIVATE_KEY` is the complete private key (including header/footer)
2. Verify the corresponding public key is in `~/.ssh/authorized_keys` on the server
3. Check file permissions:
   ```bash
   chmod 600 ~/.ssh/authorized_keys
   chmod 700 ~/.ssh
   ```
4. Verify the public key matches the private key:
   ```bash
   # Get fingerprint of private key
   ssh-keygen -l -f ~/.ssh/id_ed25519

   # Get fingerprint of public key
   ssh-keygen -l -f ~/.ssh/id_ed25519.pub

   # They should match!
   ```

### "Host key verification failed" Error

**Problem:** Server's host key not recognized

**Solution:** This is handled automatically in the workflow with `ssh-keyscan`, but if issues persist:
```bash
# On your local machine
ssh-keyscan YOUR_SERVER_IP >> ~/.ssh/known_hosts
```

### "Directory not found" Error

**Problem:** `SERVER_DEPLOY_PATH` doesn't exist or is wrong

**Solutions:**
1. Verify the path exists on your server:
   ```bash
   ls -la /opt/youtubetalker
   ```
2. Create the directory if needed:
   ```bash
   sudo mkdir -p /opt/youtubetalker
   sudo chown deploy:deploy /opt/youtubetalker
   ```
3. Update `SERVER_DEPLOY_PATH` secret if path is different

### Secrets Not Working

**Common issues:**
1. **Typo in secret name** - Must match exactly (case-sensitive)
2. **Extra spaces** - Don't add trailing spaces in secret values
3. **Wrong format** - For SSH_PRIVATE_KEY, must be complete key including headers
4. **Permissions** - Repository must have Actions enabled

## Security Best Practices

1. **Never log secrets** - GitHub Actions automatically masks secrets in logs
2. **Rotate regularly** - Change SSH keys and secrets periodically
3. **Limit access** - Only give repository admins access to secrets
4. **Use deploy keys** - For GitHub, use deploy keys instead of personal access tokens
5. **Monitor usage** - Review GitHub Actions logs regularly
6. **Principle of least privilege** - Use dedicated deploy user, not root

## Reference: Complete Secret List

| Secret Name | Type | Example Value | Required |
|-------------|------|---------------|----------|
| `SSH_PRIVATE_KEY` | SSH Key | `-----BEGIN OPENSSH PRIVATE KEY-----...` | Yes |
| `SERVER_HOST` | IP/Domain | `143.198.123.45` | Yes |
| `SERVER_USER` | Username | `deploy` | Yes |
| `SERVER_DEPLOY_PATH` | Path | `/opt/youtubetalker` | Yes |
| `CODECOV_TOKEN` | Token | `a1b2c3d4...` | No |

## Next Steps

After configuring all secrets:

1. ✅ Test SSH connection manually
2. ✅ Create a test PR to verify test workflow
3. ✅ Merge PR to test deployment workflow
4. ✅ Monitor deployment in GitHub Actions
5. ✅ Verify application is running on production server

## Support

If you encounter issues:
- Check GitHub Actions logs for detailed error messages
- Review server logs: `sudo journalctl -u youtubetalker-backend -f`
- Verify all secrets are correctly configured
- Test SSH connection manually

---

**Last Updated:** 2025-11-07
