# Add CondenseIt to your home screen

CondenseIt ships as a **Progressive Web App (PWA)**. After you install it on
your phone or tablet, it opens in its own window (no browser address bar) and
uses the same digest reader and admin panel as the desktop site.

## Before you start

1. **Open your live CondenseIt URL** in the mobile browser (for example
   `https://digest.example.com` after you deploy, or your LAN URL during local
   testing).
2. **Sign in** if your instance uses a password. The home-screen shortcut opens
   that same origin; you stay signed in until the session expires or you clear
   site data.
3. **Use HTTPS in production.** iOS and Android require a secure context for
   install prompts and reliable offline icons. Local `http://` on your LAN may
   work for testing but is not ideal for daily use.

The app manifest (`display: standalone`) and icons are served from the built
frontend (`/manifest.webmanifest`, PNG icons, and `apple-touch-icon`).

## iOS (iPhone and iPad)

Use **Safari**. Other browsers on iOS can bookmark the site, but Safari is the
reliable path for a true home-screen app.

1. Open your CondenseIt URL in Safari.
2. Tap the **Share** button (square with an upward arrow).
3. Scroll the share sheet and tap **Add to Home Screen**.
4. Edit the name if you want (default: **CondenseIt**), then tap **Add**.

The icon appears on your home screen. Launching it opens CondenseIt without
Safari’s tab bar. On smaller screens, the header includes a **Refresh** control
because installed PWAs do not get the browser’s reload button.

To remove it: long-press the icon, choose **Remove App**, then confirm.

## Android

Use **Chrome** (or another Chromium-based browser that offers “Install app”).

### Install via the menu

1. Open your CondenseIt URL in Chrome.
2. Tap the **three-dot menu** (⋮).
3. Tap **Install app** or **Add to Home screen** (wording varies by Chrome
   version and device).
4. Confirm when prompted.

Chrome may also show an **Install** banner or an install icon in the address
bar when the site meets PWA criteria. CondenseIt does not show a custom in-app
install button; use the browser UI above.

The app opens in standalone mode from your launcher or home screen. Like on
iOS, mobile layouts show a header **Refresh** button for installed use.

To remove it: long-press the icon and uninstall, or open **Settings → Apps**,
find CondenseIt (or the name you chose), and uninstall.

## Desktop (optional)

In Chrome or Edge on desktop, use the install control in the address bar
(install icon or **Install CondenseIt** in the menu) if it appears. This is
optional; many people use a normal browser tab on desktop.

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| No **Add to Home Screen** on iOS | Use Safari, not an in-app browser (Slack, Gmail, etc.). Open the URL in Safari first. |
| No **Install app** on Android | Use Chrome; update Chrome; ensure the site loads over HTTPS. |
| Wrong or missing icon | Hard-refresh once in the browser, then add again. Icons are bundled with the frontend build. |
| Logged out after install | Sign in again in the installed app; check that `DIGEST_PWA_SESSION_SECRET` (or your deploy’s session secret) is stable across server restarts on self-hosted setups. |
| Old content after a deploy | Use the header **Refresh** on mobile, or pull to refresh if your browser supports it in standalone mode. |

## Related docs

- [Getting started](getting-started.md), first run and web UI overview
- [VPS deployment](deploy-vps.md), HTTPS, domain, and production URL setup
- [Configuration](configuration.md), auth and session environment variables
