import os
import sys

def patch_file(target: str, patches: list[tuple[str, str]], patch_id: str) -> bool:
    if not os.path.isfile(target):
        return False
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    if patch_id in content:
        print(f"Already patched ({patch_id}): {target}")
        return True

    modified = content
    for old, new in patches:
        if old in modified:
            modified = modified.replace(old, new, 1)

    if modified != content:
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(modified)
        print(f"Successfully patched ({patch_id}): {target}")
        return True
    return False


def main():
    colab_cli_dirs = []

    # 1. Search uv tools paths
    for cand in [
        os.path.expandvars(r"%APPDATA%\uv\tools\google-colab-cli\Lib\site-packages\colab_cli"),
        os.path.expandvars(r"%LOCALAPPDATA%\uv\tools\google-colab-cli\Lib\site-packages\colab_cli"),
    ]:
        if os.path.isdir(cand) and cand not in colab_cli_dirs:
            colab_cli_dirs.append(cand)

    # 2. Search python environment
    try:
        import colab_cli
        for p in getattr(colab_cli, "__path__", []):
            if os.path.isdir(p) and p not in colab_cli_dirs:
                colab_cli_dirs.append(p)
    except ImportError:
        pass

    # 3. Search site-packages
    try:
        import site
        for sp in site.getsitepackages():
            cand = os.path.join(sp, "colab_cli")
            if os.path.isdir(cand) and cand not in colab_cli_dirs:
                colab_cli_dirs.append(cand)
    except Exception:
        pass

    for cli_dir in colab_cli_dirs:
        # Patch 1: console.py (termios / tty / sigwinch)
        console_path = os.path.join(cli_dir, "console.py")
        patch_file(
            console_path,
            [
                (
                    "import termios\n",
                    "# WINDOWS_COMPAT_PATCH_TERMIOS\ntry:\n    import termios\nexcept ImportError:\n    termios = None\n",
                ),
                (
                    "import tty\n",
                    "try:\n    import tty\nexcept ImportError:\n    tty = None\n",
                ),
                (
                    "is_tty = sys.stdin.isatty()",
                    "is_tty = sys.stdin.isatty() and (termios is not None) and (tty is not None)",
                ),
            ],
            "# WINDOWS_COMPAT_PATCH",
        )

        # Patch 2: commands/execution.py (cp950 UnicodeEncodeError)
        exec_path = os.path.join(cli_dir, "commands", "execution.py")
        patch_file(
            exec_path,
            [
                (
                    "        stream.write(out.get(\"text\", \"\"))\n",
                    "        # WINDOWS_COMPAT_PATCH_UNICODE\n        _txt = out.get(\"text\", \"\")\n        try:\n            stream.write(_txt)\n        except UnicodeEncodeError:\n            _enc = getattr(stream, \"encoding\", \"utf-8\") or \"utf-8\"\n            stream.write(_txt.encode(_enc, errors=\"replace\").decode(_enc, errors=\"replace\"))\n",
                ),
            ],
            "# WINDOWS_COMPAT_PATCH_UNICODE",
        )

        # Patch 3: cli.py (Force UTF-8 streams on Windows)
        cli_entry_path = os.path.join(cli_dir, "cli.py")
        patch_file(
            cli_entry_path,
            [
                (
                    "import sys\n",
                    "import sys\n# WINDOWS_COMPAT_PATCH_UTF8\nif sys.platform == 'win32':\n    if hasattr(sys.stdout, 'reconfigure'):\n        sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n    if hasattr(sys.stderr, 'reconfigure'):\n        sys.stderr.reconfigure(encoding='utf-8', errors='replace')\n",
                ),
            ],
            "# WINDOWS_COMPAT_PATCH_UTF8",
        )

if __name__ == "__main__":
    main()
