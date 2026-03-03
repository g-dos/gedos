# GitHub Webhook Setup

## Overview

Gedos can listen for GitHub Actions `workflow_run` failures and attempt an automatic local fix.

Start Gedos with the webhook server enabled:

```bash
python gedos.py --webhook
```

By default, the webhook listens on port `9876`.

## Create a GitHub Personal Access Token

1. In GitHub, open `Settings -> Developer settings -> Personal access tokens`.
2. Create a token with `repo` scope.
3. Add it to your local `.env` file:

```bash
GITHUB_TOKEN=your_token_here
```

## Configure the Webhook Secret

Choose a random secret string and set it in `.env`:

```bash
GITHUB_WEBHOOK_SECRET=your_random_secret
```

This same value must also be configured in the GitHub webhook settings.

## Add the Webhook to Your Repository

1. Open your GitHub repository.
2. Go to `Settings -> Webhooks -> Add webhook`.
3. Set:
   - Webhook URL: `http://your-mac-ip:9876/webhook`
   - Content type: `application/json`
   - Secret: your `GITHUB_WEBHOOK_SECRET`
4. Under events, choose `Workflow runs`.
5. Save the webhook.

## Expose Your Local Port

GitHub must be able to reach your Mac. If you are running locally, expose the port with ngrok:

```bash
ngrok http 9876
```

Then use the public ngrok URL in GitHub instead of your local IP:

```text
https://your-ngrok-subdomain.ngrok.app/webhook
```

## Environment Variables

Add these to `.env`:

```bash
GITHUB_TOKEN=
GITHUB_WEBHOOK_SECRET=
GITHUB_WEBHOOK_PORT=9876
```
