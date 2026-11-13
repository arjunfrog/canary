"""Entry point of the packaged app. Double-clicking Canary opens the window; arguments run a command instead."""
import sys

from canary.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["run"]))
