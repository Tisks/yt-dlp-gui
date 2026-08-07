"""Headless logic: everything the app decides that does not need a widget.

Nothing in this package imports tkinter. That is the point -- these are the
rules the UI renders, and they can be tested as plain functions in
milliseconds instead of through a live Tk window.
"""
