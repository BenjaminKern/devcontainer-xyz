#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Post-start shell configuration for devcontainer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

GREEN = "\033[0;32m"
CYAN = "\033[0;36m"
YELLOW = "\033[0;33m"
RESET = "\033[0m"


def log(msg: str, success: bool = False) -> None:
    prefix = f"{GREEN}✓ " if success else f"{CYAN}→ "
    print(f"{prefix}{msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}WARNING: {msg}{RESET}")


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


def configure_inputrc() -> None:
    log("Configuring .inputrc...")
    (Path.home() / ".inputrc").write_text("""\
set completion-ignore-case on
set show-all-if-ambiguous on
set colored-stats on
set colored-completion-prefix on
set visible-stats on
"\\e[A": history-search-backward
"\\e[B": history-search-forward
"\\e[1;5C": forward-word
"\\e[1;5D": backward-word
""")
    log("Configured .inputrc", success=True)


def create_vscode_profile() -> None:
    log("Creating .vscode_profile...")
    (Path.home() / ".vscode_profile").write_text("""\
# Bash completion
if ! shopt -oq posix; then
  [ -f /usr/share/bash-completion/bash_completion ] && . /usr/share/bash-completion/bash_completion
fi

# Git prompt
export GIT_PS1_SHOWDIRTYSTATE=1
export GIT_PS1_SHOWSTASHSTATE=1
export GIT_PS1_SHOWUNTRACKEDFILES=1
export GIT_PS1_SHOWUPSTREAM="auto"

_c_reset='\\[\\033[0m\\]'
_c_user='\\[\\033[01;32m\\]'
_c_path='\\[\\033[01;36m\\]'
_c_git='\\[\\033[01;33m\\]'

if type -t __git_ps1 &>/dev/null; then
    PS1="${_c_user}\\u${_c_reset}@\\h:${_c_path}\\w${_c_reset}${_c_git}\\$(__git_ps1 ' (%s)')${_c_reset}\\n\\$ "
else
    PS1="${_c_user}\\u${_c_reset}@\\h:${_c_path}\\w${_c_reset}\\n\\$ "
fi

# History
export HISTFILE="$HOME/.local/share/bash/history"
export HISTSIZE=10000
export HISTFILESIZE=20000
export HISTCONTROL=ignoredups:erasedups
shopt -s histappend
PROMPT_COMMAND="history -a; history -c; history -r${PROMPT_COMMAND:+; $PROMPT_COMMAND}"

# Shell options
shopt -s checkwinsize cdspell dirspell nocaseglob globstar 2>/dev/null

# Aliases
alias ll='ls -lh' la='ls -lAh' ..='cd ..' ...='cd ../..'
alias grep='grep --color=auto'
alias bz='bazelisk'

# Environment
export EDITOR="code --wait"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Bazel completion
command -v bazelisk &>/dev/null && eval "$(bazelisk completion bash)"
""")
    log("Created .vscode_profile", success=True)


def enable_vscode_profile() -> None:
    log("Enabling .vscode_profile in .bashrc...")
    bashrc = Path.home() / ".bashrc"
    content = bashrc.read_text() if bashrc.exists() else ""
    if ".vscode_profile" in content:
        log(".vscode_profile already enabled", success=True)
        return
    with bashrc.open("a") as f:
        f.write("\n[ -f ~/.vscode_profile ] && . ~/.vscode_profile\n")
    log("Enabled .vscode_profile", success=True)


def setup_precommit() -> None:
    log("Setting up pre-commit hooks...")
    git_root = get_git_root()
    if not git_root:
        warn("Not in a git repository, skipping pre-commit")
        return
    if not (git_root / ".pre-commit-config.yaml").exists():
        warn("No .pre-commit-config.yaml found, skipping")
        return
    try:
        subprocess.run(
            ["pre-commit", "install"], cwd=git_root, check=True, capture_output=True
        )
        log("Installed pre-commit hooks", success=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        warn("Failed to install pre-commit hooks")


def main() -> int:
    log("Configuring shell environment...")
    (Path.home() / ".local/share/bash").mkdir(parents=True, exist_ok=True)

    configure_inputrc()
    create_vscode_profile()
    enable_vscode_profile()
    setup_precommit()

    log("Shell environment configured!", success=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
