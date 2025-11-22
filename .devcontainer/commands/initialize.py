#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0", "psutil>=5.9.0"]
# ///
"""Initialize devcontainer environment (runs on host before container starts)."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
import yaml

GREEN = "\033[0;32m"
CYAN = "\033[0;36m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
RESET = "\033[0m"


def log(msg: str, success: bool = False) -> None:
    prefix = f"{GREEN}[OK] " if success else f"{CYAN}[..] "
    print(f"{prefix}{msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}WARNING: {msg}{RESET}")


def error(msg: str) -> None:
    print(f"{RED}ERROR: {msg}{RESET}")


def get_uid_gid() -> tuple[int, int]:
    """Get UID/GID, with fallbacks for Windows."""
    if platform.system() == "Windows":
        return 1000, 1000  # Default values for Docker on Windows
    return os.getuid(), os.getgid()


@dataclass
class SystemInfo:
    ptrace_scope: int | None
    disk_available_gb: int | None
    memory_total_gb: int
    memory_available_gb: int
    docker_available: bool
    docker_running: bool
    docker_version: str | None
    git_repo_root: Path | None


def get_git_root() -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_system_info() -> SystemInfo:
    # Disk
    disk_gb = None
    try:
        disk_gb = psutil.disk_usage("/var").free // (1024**3)
    except (PermissionError, FileNotFoundError):
        pass

    # Memory
    mem = psutil.virtual_memory()

    # Docker
    docker_available = shutil.which("docker") is not None
    docker_running = False
    docker_version = None
    if docker_available:
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, check=True
            )
            docker_version = result.stdout.strip()
            subprocess.run(["docker", "info"], capture_output=True, check=True)
            docker_running = True
        except subprocess.CalledProcessError:
            pass

    # Ptrace
    ptrace = None
    try:
        ptrace = int(Path("/proc/sys/kernel/yama/ptrace_scope").read_text().strip())
    except (FileNotFoundError, ValueError):
        pass

    return SystemInfo(
        ptrace_scope=ptrace,
        disk_available_gb=disk_gb,
        memory_total_gb=mem.total // (1024**3),
        memory_available_gb=mem.available // (1024**3),
        docker_available=docker_available,
        docker_running=docker_running,
        docker_version=docker_version,
        git_repo_root=get_git_root(),
    )


def validate_host() -> bool:
    log("Validating host system...")
    info = get_system_info()
    failed = False

    # Ptrace
    if info.ptrace_scope is not None:
        levels = {0: "unrestricted", 1: "restricted", 2: "admin-only", 3: "disabled"}
        desc = levels.get(info.ptrace_scope, "unknown")
        if info.ptrace_scope == 0:
            log(f"ptrace_scope: {info.ptrace_scope} ({desc})", success=True)
        elif info.ptrace_scope == 3:
            error(f"ptrace_scope: {info.ptrace_scope} ({desc})")
            failed = True
        else:
            warn(f"ptrace_scope: {info.ptrace_scope} ({desc})")

    # Docker
    if not info.docker_available:
        error("Docker not found")
        failed = True
    elif not info.docker_running:
        error("Docker daemon not running")
        failed = True
    else:
        log(f"Docker: {info.docker_version or 'available'}", success=True)

    # Resources
    if info.disk_available_gb is not None:
        if info.disk_available_gb < 10:
            warn(f"Disk: {info.disk_available_gb}GB available (low)")
        else:
            log(f"Disk: {info.disk_available_gb}GB available", success=True)

    if info.memory_available_gb < 2:
        warn(f"Memory: {info.memory_available_gb}GB available (low)")
    else:
        log(
            f"Memory: {info.memory_available_gb}/{info.memory_total_gb}GB", success=True
        )

    # Git
    if info.git_repo_root:
        log(f"Git: {info.git_repo_root}", success=True)
    else:
        warn("Git repository not found")

    return not failed


def validate_yaml(path: Path, validator: Any) -> bool:
    log(f"Validating {path.name}...")
    if not path.exists():
        error(f"File not found: {path}")
        return False
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            error(f"{path.name}: Invalid YAML (expected dict)")
            return False
        if validator(data, path.name):
            log(f"{path.name}: Valid", success=True)
            return True
        return False
    except yaml.YAMLError as e:
        error(f"{path.name}: YAML error: {e}")
        return False


def validate_compose(data: dict, filename: str) -> bool:
    if "services" not in data or "devcontainer" not in data.get("services", {}):
        error(f"{filename}: Missing services.devcontainer")
        return False
    return True


def validate_compose_custom(data: dict, filename: str) -> bool:
    if not validate_compose(data, filename):
        return False
    allowed = {"environment", "volumes", "devices", "ports", "cap_add", "extra_hosts"}
    unknown = set(data["services"]["devcontainer"].keys()) - allowed
    if unknown:
        warn(f"{filename}: Unknown keys: {', '.join(sorted(unknown))}")
    return True


def validate_packages(data: dict, filename: str) -> bool:
    for field in ("image_name", "image_tag"):
        if field not in data or not isinstance(data[field], str):
            error(f"{filename}: Missing or invalid '{field}'")
            return False
    if "base" not in data or not isinstance(data.get("base", {}).get("packages"), list):
        error(f"{filename}: Missing or invalid 'base.packages'")
        return False
    return True


def validate_packages_custom(data: dict, filename: str) -> bool:
    allowed = {"base", "devenv"}
    unknown = set(data.keys()) - allowed
    if unknown:
        warn(f"{filename}: Unknown sections: {', '.join(sorted(unknown))}")
    return True


def create_compose_custom(path: Path) -> None:
    log(f"Creating {path.name}...")
    content = """\
# Custom docker-compose overrides
# Examples: environment, volumes, devices, ports, extra_hosts

services:
  devcontainer:
    environment: []
    volumes: []
    devices: []
"""
    path.write_text(content)
    log(f"Created {path.name}", success=True)


def create_packages_custom(path: Path) -> None:
    log(f"Creating {path.name}...")
    content = """\
# Custom package overrides (merged with packages.default.yml)

base:
  packages: []

devenv:
  packages: []
"""
    path.write_text(content)
    log(f"Created {path.name}", success=True)


def merge_packages(default_path: Path, custom_path: Path, output_path: Path) -> None:
    """Merge default and custom package configs into packages.yml."""
    log("Merging package configurations...")

    with default_path.open() as f:
        merged = yaml.safe_load(f)

    if custom_path.exists():
        with custom_path.open() as f:
            custom = yaml.safe_load(f) or {}

        # Merge base section
        if "base" in custom:
            if "packages" in custom["base"]:
                merged.setdefault("base", {}).setdefault("packages", [])
                merged["base"]["packages"].extend(custom["base"]["packages"])
            if "python_tools" in custom["base"]:
                merged.setdefault("base", {}).setdefault("python_tools", [])
                merged["base"]["python_tools"].extend(custom["base"]["python_tools"])

        # Merge devenv section
        if "devenv" in custom:
            if "packages" in custom["devenv"]:
                merged.setdefault("devenv", {}).setdefault("packages", [])
                merged["devenv"]["packages"].extend(custom["devenv"]["packages"])
            if "python_tools" in custom["devenv"]:
                merged.setdefault("devenv", {}).setdefault("python_tools", [])
                merged["devenv"]["python_tools"].extend(
                    custom["devenv"]["python_tools"]
                )

    with output_path.open("w") as f:
        yaml.dump(merged, f, default_flow_style=False, sort_keys=False)

    log(f"Created {output_path.name}", success=True)


def generate_env(env_path: Path, packages_path: Path, suffix: str) -> None:
    log("Generating .env...")
    lines: list[str] = []

    # Proxy
    for var in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
        for v in (var, var.upper()):
            if val := os.environ.get(v):
                lines.append(f"{v}={val}")
    if lines:
        lines.append("")

    # User
    username = os.environ.get("USER", os.environ.get("USERNAME", "developer"))
    uid, gid = get_uid_gid()
    lines.extend(
        [
            f"SHELL={os.environ.get('SHELL', '/bin/bash')}",
            f"USER={username}",
            f"USER_UID={uid}",
            f"USER_GID={gid}",
        ]
    )

    # Image config from packages.yml
    try:
        with packages_path.open() as f:
            pkg = yaml.safe_load(f)
        image_name = pkg.get("image_name", "ubuntu")
        image_tag = pkg.get("image_tag", "24.04")
    except Exception:
        image_name, image_tag = "ubuntu", "24.04"

    lines.extend(
        [
            "",
            f"IMAGE_NAME={image_name}",
            f"IMAGE_TAG={image_tag}",
            "",
            "BUILD_TARGET=devenv",
        ]
    )

    # Service names
    suffix_part = f"-{suffix}" if suffix else ""
    lines.extend(
        [
            "",
            f"SERVICE_PREPARE={username}-devcontainer-prepare{suffix_part}",
            f"SERVICE_MAIN={username}-devcontainer{suffix_part}",
            "",
            f"VOLUME_LOCAL_SHARE={username}-devcontainer-local-share{suffix_part}",
            f"VOLUME_CONFIG={username}-devcontainer-config{suffix_part}",
            f"VOLUME_CACHE={username}-devcontainer-cache{suffix_part}",
            f"VOLUME_VSCODE_EXT={username}-vscode-extensions{suffix_part}",
            f"VOLUME_VSCODE_EXT_INSIDERS={username}-vscode-extensions-insiders{suffix_part}",
            "",
            # Use POSIX paths (forward slashes) for Docker compatibility on Windows
            f"HOME={Path.home().as_posix()}",
        ]
    )

    if git_root := get_git_root():
        lines.append(f"GIT_REPO_ROOT={git_root.as_posix()}")

    env_path.write_text("\n".join(lines) + "\n")
    log(f"Generated .env (UID={uid}, GID={gid})", success=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize devcontainer environment")
    parser.add_argument("devcontainer_dir", type=Path, help="Path to .devcontainer")
    parser.add_argument("--suffix", default="", help="Service name suffix")
    args = parser.parse_args()

    docker_dir = args.devcontainer_dir / "docker"
    if not docker_dir.is_dir():
        error(f"Directory not found: {docker_dir}")
        return 1

    validate_host()

    # Validate compose
    log("Validating Docker configuration...")
    if not validate_yaml(docker_dir / "docker-compose.default.yml", validate_compose):
        return 1

    compose_custom = docker_dir / "docker-compose.custom.yml"
    if compose_custom.exists():
        if not validate_yaml(compose_custom, validate_compose_custom):
            return 1
    else:
        create_compose_custom(compose_custom)

    # Validate packages
    log("Validating package configuration...")
    packages_default = docker_dir / "packages.default.yml"
    if not validate_yaml(packages_default, validate_packages):
        return 1

    packages_custom = docker_dir / "packages.custom.yml"
    if packages_custom.exists():
        if not validate_yaml(packages_custom, validate_packages_custom):
            return 1
    else:
        create_packages_custom(packages_custom)

    # Merge packages into packages.yml (used by Dockerfile)
    packages_merged = docker_dir / "packages.yml"
    merge_packages(packages_default, packages_custom, packages_merged)

    # Ensure host files exist for mounting
    (Path.home() / ".netrc").touch(exist_ok=True)
    (Path.home() / ".gitconfig").touch(exist_ok=True)

    # Generate .env
    log("Initializing environment...")
    env_path = docker_dir / ".env"
    env_path.unlink(missing_ok=True)
    generate_env(env_path, packages_merged, args.suffix)

    log("Environment initialized!", success=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
