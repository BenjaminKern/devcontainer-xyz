# devcontainer-xyz

A flexible, production-ready devcontainer template with automatic customization, lazy-loaded tools, and optimized performance.

## Features

- **🚀 Multi-stage builds**: Separate base (production) and devenv (development) layers for optimized container sizes
- **⚡ Lazy-loaded tools**: Python tools installed on-demand via uvx for faster startup times
- **🔧 Easy customization**: Override packages and compose settings without modifying template files
- **👤 UID/GID matching**: Automatic host user ID mapping to avoid permission issues
- **💾 Persistent volumes**: Named Docker volumes for configs, caches, and VS Code extensions
- **✅ Pre-flight validation**: Automatic system checks before container startup
- **🎨 Enhanced shell**: Git-aware prompt, bash completion, and sensible defaults

## Quick Start

### Prerequisites

- Docker Engine (Linux/macOS) or Docker Desktop with WSL2 backend (Windows)
- VS Code with [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

> **Windows users**: See [Windows Host Requirements](#windows-host-requirements) for important setup instructions.

### Usage

1. **Use this template** or clone it:
   ```bash
   git clone https://github.com/yourusername/devcontainer-xyz.git my-project
   cd my-project
   ```

2. **Open in VS Code**:
   ```bash
   code .
   ```

3. **Start the devcontainer**:
   - Press `F1` or `Cmd/Ctrl+Shift+P`
   - Select "Dev Containers: Reopen in Container"
   - Wait for initialization (first build takes 2-5 minutes)

4. **Start coding!** The container includes:
   - Git, curl, and essential tools
   - uv (Python package manager)
   - Bazelisk (Bazel build tool)
   - Pre-commit (if `.pre-commit-config.yaml` exists)

## Customization

### Adding System Packages

Create or edit `.devcontainer/docker/packages.custom.yml`:

```yaml
base:
  packages:
    - build-essential  # Available in both base and devenv
  python_tools:
    - ruff  # Lazy-loaded Python tools for base layer

devenv:
  packages:
    - vim
    - htop
  python_tools:
    - black
    - mypy
```

### Adding Environment Variables or Volumes

Create or edit `.devcontainer/docker/docker-compose.custom.yml`:

```yaml
services:
  devcontainer:
    environment:
      - NODE_ENV=development
      - API_URL=http://localhost:3000

    volumes:
      - ~/.ssh:/home/${USER}/.ssh:ro  # Mount SSH keys

    devices:
      - /dev/fuse  # Enable FUSE support

    ports:
      - "3000:3000"  # Expose ports
```

### Changing Base Image

Edit `.devcontainer/docker/packages.custom.yml` to override the image:

```yaml
image_name: ubuntu
image_tag: "22.04"
```

Or use a different base entirely:

```yaml
image_name: debian
image_tag: "bookworm-slim"
```

## How It Works

### Architecture

```
┌─────────────────────────────────────────┐
│  Host (macOS/Linux/Windows)             │
│  ├─ .devcontainer/                      │
│  │  ├─ commands/                        │
│  │  │  ├─ initialize.py (pre-start)     │
│  │  │  └─ post_start.py (post-start)    │
│  │  └─ docker/                          │
│  │     ├─ Dockerfile (multi-stage)      │
│  │     ├─ packages.default.yml          │
│  │     ├─ packages.custom.yml (yours)   │
│  │     └─ docker-compose.*.yml          │
└─────────────────────────────────────────┘
           │
           ▼ (initialize.py validates & merges configs)
           │
           ▼ (Docker builds base → devenv)
           │
┌─────────────────────────────────────────┐
│  Container (Ubuntu 24.04)               │
│  ├─ Base Layer:                         │
│  │  ├─ Essential tools (git, curl)      │
│  │  ├─ yq, uv, bazelisk                 │
│  │  └─ Python tools (lazy-loaded)       │
│  ├─ DevEnv Layer:                       │
│  │  ├─ Development packages             │
│  │  └─ Additional Python tools          │
│  └─ Named Volumes:                      │
│     ├─ config (~/.config)               │
│     ├─ cache (~/.cache)                 │
│     └─ vscode-ext (extensions)          │
└─────────────────────────────────────────┘
           │
           ▼ (post_start.py configures shell & git)
           │
           ▼ Ready for development!
```

### Lazy-Loading Python Tools

Python tools are installed via `uvx-shim`, which means they're only downloaded and installed the first time you run them:

```bash
# First run: installs black
black --version

# Subsequent runs: instant
black --version
```

Add tools to `python_tools` lists in `packages.custom.yml` to make them available.

### Configuration Merging

The initialization script merges configurations:
- `packages.default.yml` + `packages.custom.yml` → `packages.yml`
- `docker-compose.default.yml` + `docker-compose.custom.yml` → used by Docker Compose

This allows you to customize without modifying template files, making updates easier.

### UID/GID Matching

The container automatically creates a user matching your host UID/GID:
- Prevents "permission denied" errors
- Files created in container have correct ownership on host
- Works seamlessly with git commits and file operations

## Project Structure

```
.
├── .devcontainer/
│   ├── devcontainer.json           # VS Code devcontainer config
│   ├── commands/
│   │   ├── initialize.py           # Pre-start validation & setup
│   │   └── post_start.py           # Shell & git configuration
│   └── docker/
│       ├── Dockerfile              # Multi-stage build definition
│       ├── packages.default.yml    # Default package list
│       ├── packages.custom.yml     # Your customizations (gitignored)
│       ├── docker-compose.default.yml
│       └── docker-compose.custom.yml  # Your overrides (gitignored)
└── .gitignore
```

## Troubleshooting

### Windows Host Requirements

This devcontainer runs **Linux containers**, which requires specific Docker configuration on Windows:

#### Requirements

1. **Docker Desktop** (not just Docker Engine)
2. **WSL2 backend enabled** - Docker Desktop must use WSL2, not Hyper-V
3. **Linux containers mode** - Docker must be set to run Linux containers (not Windows containers)

#### Verification

```powershell
docker info | findstr "OSType"
# Should output: OSType: linux
```

If it shows `OSType: windows`, you're in Windows containers mode and need to switch.

View initialization logs:
```bash
# The initialize.py script outputs detailed validation info
# Check VS Code's "Dev Containers" output panel
```

### Permission issues

Rebuild to refresh UID/GID mapping:
- Command Palette → "Dev Containers: Rebuild Container"

### Slow startup

First build downloads packages and can take time. Subsequent starts should be fast (<10 seconds). If using many Python tools, they'll install lazily on first use.

### Custom packages not appearing

1. Check `.devcontainer/docker/packages.custom.yml` syntax
2. Rebuild container (don't just reload)
3. Check build logs for errors

## Advanced Usage

### Using the Base Layer Only

For production or CI, target the base layer:

```bash
docker build \
  --target base \
  -t my-app:base \
  -f .devcontainer/docker/Dockerfile \
  .devcontainer/docker/
```

### Manual Initialization

Run the initialization script outside VS Code:

```bash
.devcontainer/commands/initialize.py .devcontainer --suffix test
```

### Multiple Containers

The `--suffix` parameter allows multiple isolated containers:
- Different branches: `--suffix feature-x`
- Different projects: `--suffix project-a`

Each gets separate volumes and container names.

## Contributing

Contributions welcome! This template is designed to be:
- **Minimal**: Only essential tools in base layer
- **Flexible**: Easy to customize without forking
- **Fast**: Optimized builds and lazy-loading
- **Reliable**: Validated configs and error handling

## License

MIT License - see LICENSE file for details

## Acknowledgments

Built with:
- [Dev Containers](https://containers.dev/) specification
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
- [Bazelisk](https://github.com/bazelbuild/bazelisk) - Bazel version manager
- [yq](https://github.com/mikefarah/yq) - YAML processor
