# Docker Issues

## Symptom 1: "Docker daemon not running"

**What you see:**

```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

## Solution

Start Docker Desktop (macOS/Windows) or the Docker daemon (Linux):

**macOS/Windows:**
- Open Docker Desktop application
- Wait for it to fully start (whale icon in system tray)

**Linux:**
```bash
sudo systemctl start docker
```

Verify Docker is running:

```bash
docker ps
```

## Symptom 2: Container Exits Immediately

**What happens:**

```bash
docker compose up -d
# Container starts then immediately exits

docker ps
# snowplow-micro is not listed
```

## Diagnosis

Check container logs:

```bash
docker logs snowplow-micro
```

### Common Exit Causes

#### Memory Constraints

**Log shows:**
```
Cannot allocate memory
Killed
```

**Solution:** Increase Docker memory limit

- Docker Desktop: Settings → Resources → Memory (increase to at least 2GB)
- Linux: Check available memory with `free -h`

#### Image Pull Failure

**Log shows:**
```
Error response from daemon: manifest for snowplow/snowplow-micro:2.1.2 not found
```

**Solution:** Pull image manually

```bash
docker pull snowplow/snowplow-micro:2.1.2
```

Check available tags at [Docker Hub](https://hub.docker.com/r/snowplow/snowplow-micro/tags).

#### Configuration Error

**Log shows errors about config files**

**Solution:** Check your docker-compose.yml for syntax errors:

```bash
docker compose config  # Validates compose file
```

## Symptom 3: "docker compose: command not found"

**What you see:**

```
bash: docker compose: command not found
```

## Diagnosis

Check Docker Compose version:

```bash
docker compose version  # Compose v2 (built-in)
docker-compose version  # Compose v1 (standalone)
```

## Solution

### If you have Compose v1 (docker-compose):

Use `docker-compose` instead of `docker compose`:

```bash
docker-compose up -d
```

### If you have neither:

**Install Docker Compose:**

- **macOS/Windows:** Update Docker Desktop (includes Compose v2)
- **Linux:** Follow [official installation guide](https://docs.docker.com/compose/install/)

## Symptom 4: Network Issues

**What happens:**

Container starts but can't reach external resources (enrichment databases, etc.).

**Log shows:**

```
Could not resolve host
Connection refused
```

## Diagnosis

Check network connectivity from container:

```bash
docker exec snowplow-micro ping -c 3 google.com
```

## Solution

Check Docker network settings:

```bash
# Restart Docker networking
docker network prune
docker compose down
docker compose up -d
```

On corporate networks, configure Docker to use proxy settings.

## Symptom 5: Volume Mount Issues on Windows

**What happens:**

Schemas or enrichments don't appear in container.

**Logs show:**

```
No such file or directory
```

## Diagnosis

Windows path issues - Docker expects forward slashes.

## Solution

Use forward slashes in docker-compose.yml:

```yaml
# Wrong
volumes:
  - C:\Users\Name\schemas:/config/schemas

# Correct
volumes:
  - C:/Users/Name/schemas:/config/schemas
```

Or use WSL2 paths:

```yaml
volumes:
  - /mnt/c/Users/Name/schemas:/config/schemas
```

Also ensure Docker Desktop has access to the drive:
- Docker Desktop → Settings → Resources → File Sharing
- Add the drive (e.g., C:)

## Symptom 6: "Cannot Remove Container"

**What you see:**

```
Error response from daemon: cannot remove container: container is running
```

## Solution

Stop and remove forcefully:

```bash
docker stop snowplow-micro
docker rm -f snowplow-micro

# Or with compose
docker compose down
```

## Symptom 7: Image Architecture Mismatch

**What happens (especially on Apple Silicon):**

```
WARNING: The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8)
```

Container may run slowly or not at all.

## Solution

Specify platform in docker-compose.yml:

```yaml
services:
  micro:
    platform: linux/amd64  # or linux/arm64 depending on availability
    image: snowplow/snowplow-micro:2.1.2
```

Check [Docker Hub](https://hub.docker.com/r/snowplow/snowplow-micro/tags) for available architectures.

## General Debugging Steps

When Micro won't start or work correctly:

1. **Check Docker is running:**
   ```bash
   docker ps
   ```

2. **View container status:**
   ```bash
   docker compose ps
   ```

3. **Check logs:**
   ```bash
   docker logs snowplow-micro
   docker logs --follow snowplow-micro  # Follow logs in real-time
   ```

4. **Inspect container:**
   ```bash
   docker inspect snowplow-micro
   ```

5. **Try a fresh start:**
   ```bash
   docker compose down
   docker compose pull  # Get latest image
   docker compose up -d
   ```

6. **Check resource usage:**
   ```bash
   docker stats snowplow-micro
   ```

## Getting Help

If issues persist, gather diagnostic info:

```bash
# Docker version
docker --version
docker compose version

# System info
uname -a  # Linux/Mac
systeminfo  # Windows

# Container logs
docker logs snowplow-micro > micro-logs.txt

# Compose config
docker compose config > compose-config.txt
```

Include this info when asking for help.
