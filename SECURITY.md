# Security policy

## Report a vulnerability

Do not open a public issue for a security problem. Use
[GitHub private vulnerability reporting](https://github.com/SuzalShrestha/cam-watch/security/advisories/new).
You get a reply in 7 days.

## Supported versions

Only the latest version on the `main` branch gets fixes.

## Keep your setup safe

- The config file holds your camera password and Telegram token: `chmod 600` it, and never share it.
- Error logs can show the stream URL with the camera login. Do not post logs before you remove it.
- Do not expose your camera or this computer to the internet. Use a VPN (for example WireGuard or Tailscale) for remote access.
- Change the default password of your camera.
