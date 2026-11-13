"""The desktop app: a native window built with PySide6 (Qt). Runs on macOS and Windows.

There is no web server and no browser. The window reads the local database directly,
and a background thread runs the worker and (later) the Telegram listener.
"""
