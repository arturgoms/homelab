# srv backup

Automated daily backup of `/srv` homelab data to a NAS. Runs as a systemd timer at 3:00 AM.

## How it works

The backup runs in 4 steps:

| Step | Name | What it does | Duration |
|------|------|-------------|----------|
| 1 | `db` | Dumps all databases (MariaDB, PostgreSQL, InfluxDB) | ~1 min |
| 2 | `sync` | Rsync mirrors `/srv` to NAS (`latest/`) | ~2 hrs first run, minutes after |
| 3 | `rotate` | Copies DB dumps to day-of-week folder, cleans up local dumps | ~1 min |
| 4 | `volumes` | Exports Docker named volumes as tar.gz to day-of-week folder | ~5 min |

### Rotation strategy

- **Files & configs**: rsync mirror in `latest/` (always the most recent state)
- **DB dumps & volumes**: rotated by day of week (`day-0` to `day-6`), giving 7 days of history

### NAS structure

```
/mnt/friday-pool/all/media/backups/srv1/
  latest/          # rsync mirror of /srv (updated daily)
  dumps/
    day-0/         # Sunday
      db-dumps/    # database dumps
      volumes/     # Docker volume tar.gz files
    day-1/         # Monday
    ...
    day-6/         # Saturday
  logs/            # backup logs (auto-cleaned after retention_days)
```

## Setup

```bash
sudo /srv/backup/install.sh
```

This will:
1. Install `rsync` and `yq`
2. Make scripts executable
3. Symlink systemd units to `/etc/systemd/system/`
4. Enable the daily timer

## Configuration

Edit `config.yml` to change any parameters:

### Paths & retention

```yaml
source_dir: /srv                                          # what to back up
backup_dest: /mnt/friday-pool/all/media/backups/srv1      # where to store backups
retention_days: 7                                         # log cleanup after N days
```

### Rsync exclusions

Add patterns for files/directories that don't need backing up:

```yaml
rsync_excludes:
  - node_modules
  - .git
  - venv
  - .venv
  # ...
```

### Adding a database

Add an entry under `databases`:

```yaml
databases:
  - name: my-db                    # identifier (used in dump filenames)
    container: my-container        # Docker container name
    format: sql                    # sql (stdout redirect) or dir (directory backup)
    dump_dir: /srv/my-service/dumps
    dump_cmd: 'pg_dumpall -U myuser'          # runs inside the container
    restore_cmd: 'psql -U myuser'             # runs inside the container for restore
```

**Formats:**
- `sql` - dump command writes to stdout, saved as `.sql` file (MariaDB, PostgreSQL)
- `dir` - dump command writes to `/tmp/backup` inside container, then `docker cp` pulls it out (InfluxDB)

### Adding a Docker volume

Add the volume name under `docker_volumes`:

```yaml
docker_volumes:
  - my-service_my-volume
```

Find volume names with: `docker volume ls --format '{{.Name}}'`

## Usage

### Manual backup

```bash
# Full backup
sudo /srv/backup/backup.sh

# Skip specific steps
sudo /srv/backup/backup.sh --skip=sync        # skip the long rsync
sudo /srv/backup/backup.sh --skip=db --skip=sync

# Run only one step
sudo /srv/backup/backup.sh --only=db          # just dump databases
sudo /srv/backup/backup.sh --only=volumes     # just export volumes
```

Steps: `db`, `sync`, `rotate`, `volumes`

### Check timer status

```bash
systemctl status srv-backup.timer
systemctl list-timers srv-backup.timer
```

### View logs

```bash
ls /mnt/friday-pool/all/media/backups/srv1/logs/
```

## Restore

```bash
# List available backups
/srv/backup/restore.sh list

# List a specific day's backups
/srv/backup/restore.sh list 3

# Restore service files from latest mirror
/srv/backup/restore.sh files navidrome

# Restore a database dump from a specific day (0=Sun, 6=Sat)
/srv/backup/restore.sh db mariadb 3
/srv/backup/restore.sh db postgres 3

# Restore a Docker volume from a specific day
/srv/backup/restore.sh volume n8n_n8n_storage 1
```

## Files

| File | Description |
|------|-------------|
| `config.yml` | All configurable parameters |
| `backup.sh` | Main backup script |
| `restore.sh` | Restore helper |
| `install.sh` | One-time setup (deps, systemd) |
| `srv-backup.service` | Systemd service unit |
| `srv-backup.timer` | Systemd timer unit |
