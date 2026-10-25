"""Point the packaged backend's symbolic links back inside the app.

Electron Packager copies the PyInstaller backend (--extra-resource) and turns
its relative symbolic links into absolute ones that point at the build
machine (e.g. /Users/runner/.../dist/backend-macos/...). On a user's computer
those targets do not exist: on macOS this includes _internal/Python, the
Python runtime the backend starts from, and codesign rejects the bundle.

Every link under the packaged backend whose target lies in the source
backend directory is rewritten as a relative link to the same place inside
the package. Links to anywhere else are reported and make the script fail.

Usage:
    python3 scripts/relativize_backend_links.py <packaged backend dir> <source backend dir>
"""

import os
import sys


def main() -> int:
    packaged, source = (os.path.abspath(p) for p in sys.argv[1:3])
    source_real = os.path.realpath(source)
    fixed, bad = 0, []
    for dirpath, dirnames, filenames in os.walk(packaged):
        for name in dirnames + filenames:
            link = os.path.join(dirpath, name)
            if not os.path.islink(link):
                continue
            target = os.readlink(link)
            if not os.path.isabs(target):
                continue
            for base in (source, source_real):
                if target == base or target.startswith(base + os.sep):
                    inside = os.path.join(packaged, os.path.relpath(target, base))
                    os.unlink(link)
                    os.symlink(os.path.relpath(inside, os.path.dirname(link)), link)
                    fixed += 1
                    break
            else:
                bad.append(f"{link} -> {target}")
    print(f"relativized {fixed} backend link(s)")
    for line in bad:
        print(f"  link leaves the package: {line}")
    dangling = [os.path.join(d, n) for d, ds, fs in os.walk(packaged) for n in ds + fs
                if os.path.islink(os.path.join(d, n)) and not os.path.exists(os.path.join(d, n))]
    for link in dangling:
        print(f"  dangling link: {link} -> {os.readlink(link)}")
    return 1 if bad or dangling else 0


if __name__ == "__main__":
    sys.exit(main())
