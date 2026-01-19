---
title: "How to Manage Passwords"
description: "My approach to password management - tools, synchronization, organization, and security practices"
date: 2026-01-19
tags:
  - security
  - passwords
  - keepass
  - self-hosted
---

This is my approach to password management - the tools I use, synchronization setup, folder organization, review routines, and security practices. A practical guide to managing passwords efficiently while maintaining a high level of security.

## Tools and Clients

### KeePass as the Core

I use KeePass as my primary password manager. It securely stores all passwords in an encrypted database that is unlocked with a master key. The database file is encrypted using AES-256, ChaCha20, and Twofish - the best encryption algorithms currently known.

### Strongbox on macOS and iOS

On my Apple devices, I use Strongbox as a KeePass client. What I love most about Strongbox is its **built-in SSH agent** - it can use a key that lives inside the KeePass database to facilitate secure SSH authentication. No more managing separate SSH keys.

## Synchronization

To keep my password database available offline yet synchronized across all devices, I use a self-hosted Nextcloud instance.

### Nextcloud Clients

I run the Nextcloud client on my iPhone, MacBook, and Windows machine. Any new password creation or changes in the database are seamlessly updated across platforms.

### Sync Alternatives I Tested

I experimented with other sync methods:

- **Syncthing** - Good for peer-to-peer, but less convenient for mobile
- **Git** - Works well but overkill for a single file
- **iCloud** - Convenient but less control over my data

Nextcloud proved to be the most practical solution, providing a balance between accessibility, security, and control over my data. Plus, it's self-hosted on my [[projects/homelab|homelab]].

## Folder Organization

The KeePass database is structured into folders to keep everything organized:

```
├── Inbox          # Uncategorized passwords
├── 3rd Party      # Passwords that don't belong to me
├── Favorites      # Most frequently accessed (GitHub, Apple)
├── Personal       # All personal passwords
│   └── Homelab    # Homelab-specific credentials
└── Work           # Segmented by company
    ├── Company A
    ├── Company B
    └── Company C
```

### Inbox

Passwords that haven't been categorized yet. New entries go here first.

### 3rd Party

Passwords that don't belong to me - shared credentials, client systems, etc.

### Favorites

A small selection of most frequently accessed passwords. Currently just GitHub and Apple for quick access.

### Personal

All my personal passwords, with a subfolder dedicated to homelab tools and services.

### Work

Contains passwords segmented by company I work for, each in its own subfolder.

## Maintenance and Security Practices

### Weekly Review Process

I conduct a weekly review to:
- Recategorize passwords from Inbox to proper folders
- Remove old or unused entries
- Check for weak or reused passwords
- Ensure everything stays organized

### Enhanced Security

- **Two-factor authentication** enabled wherever possible
- **Passkeys over passwords** - I prefer passkeys when available and am in the process of migrating
- **Random generation** - Moving away from reused passwords to randomly generated ones

### Backup and Offline Availability

The entire password database is:
- Kept offline on each device
- Synced securely via self-hosted Nextcloud
- Automatically backed up through Nextcloud's versioning

This provides a robust backup system that is both secure and easily accessible across all my devices.

## Why This Setup?

1. **Control** - I own my data. No third-party cloud service has my passwords.
2. **Offline access** - Works without internet. The database lives locally.
3. **Cross-platform** - KeePass format works everywhere with different clients.
4. **SSH integration** - Strongbox's SSH agent is a killer feature.
5. **Self-hosted sync** - Nextcloud gives me Dropbox-like convenience with full control.

## Getting Started

1. Download KeePass or KeePassXC
2. Create a database with a strong master password
3. Set up your folder structure
4. Install clients on all your devices (Strongbox, KeePassDX, etc.)
5. Configure sync via Nextcloud, Syncthing, or your preferred method
6. Establish a weekly review habit

The initial setup takes some effort, but the result is a password management system you fully control.
