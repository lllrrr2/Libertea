<img src="https://raw.githubusercontent.com/VZiChoushaDui/Libertea/master/docs/logo-complete.png" style="width: 300px" />

# Libertea

Easily install and manage a Clash VPN server.

## Features

- One-command installation and management
- User management
- TROJAN and VLESS protocols
- Auto select the fastest route on user's devices
- Multiple domains behind CDN
- Secondary proxies for better availability

## Requirements

- Ubuntu 20.04 or higher (Ubuntu 22.04 recommended)
- At least one domain behind a CDN (Cloudflare recommended)

## Recommended configuration

- Two domains behind a CDN (Cloudflare recommended), one for the panel/update and one for the VPN itself
- An extra server for the secondary proxy

## Installation

To install, run the following command on your server:

    curl -s https://raw.githubusercontent.com/VZiChoushaDui/Libertea/master/bootstrap.sh -o /tmp/bootstrap.sh && bash /tmp/bootstrap.sh install

## Update

To update, run the following command on your server:

    curl -s https://raw.githubusercontent.com/VZiChoushaDui/Libertea/master/bootstrap.sh -o /tmp/bootstrap.sh && bash /tmp/bootstrap.sh update
