"""Which tabs are on screen, worked out without touching a widget.

Aqua gives a ttk.Notebook no tab overflow of its own: the strip simply grows
until the tabs run off the window. The app pages through them instead, hiding
whatever falls outside the current page. Every decision about where that page
sits lives here as arithmetic over integers.

Keeping it separate from the notebook is deliberate. This is the most intricate
state in the app -- an off-by-one strands the last tab out of reach -- and it is
far cheaper to pin down as arithmetic than through a live notebook.
"""


def clamp_start(page_start, total, page_size):
    """Keep a page start inside the range that leaves a full page visible."""
    return max(0, min(page_start, total - page_size))


def visible_window(total, page_start, selected, page_size):
    """The (start, end) slice of tabs that should be on screen.

    `selected` (an index, or None when the '+' tab is selected) always wins:
    the selected tab must stay reachable, so the page is dragged to it. Doing
    that here rather than on the selection event covers every route in --
    clicking, adding, closing, and auto-close removing a tab.
    """
    if total <= page_size:
        return 0, total

    start = clamp_start(page_start, total, page_size)
    if selected is not None:
        if selected < start:
            start = selected
        elif selected >= start + page_size:
            start = selected - page_size + 1
        start = clamp_start(start, total, page_size)

    return start, start + page_size


def turn_page(page_start, direction, total, page_size):
    """Where the page starts after one turn left (-1) or right (+1)."""
    if total <= page_size:
        return 0
    # Overlap one tab per turn, so there is a shared landmark between pages.
    step = direction * max(1, page_size - 1)
    return clamp_start(page_start + step, total, page_size)


def landing_index(selected, start, end):
    """Which tab to select when `selected` would fall off the [start, end) page.

    None means the selection is already on the page and should be left alone.
    """
    if selected is None or start <= selected < end:
        return None
    return min(max(selected, start), end - 1)


def offscreen_text(start, end, total):
    """The pager's annotation: how many tabs sit off each side."""
    parts = []
    if start:
        parts.append(f"{start} before")
    if total - end:
        parts.append(f"{total - end} after")
    return "  " + ", ".join(parts) if parts else ""


def tab_label(number, glyph, closable, close_glyph):
    """A tab's caption: its number, any status glyph, and the close affordance.

    Just the number rather than "Batch N" -- at roughly half the width it is the
    difference between five tabs fitting on screen and eleven.
    """
    label = str(number)
    if glyph:
        label += f" {glyph}"
    if closable:
        label += f"   {close_glyph}"
    return label


def next_tab_number(numbers):
    """The number to give a new tab, from the numbers already open.

    Derived from the open tabs rather than a running counter: after opening and
    closing 30 tabs the next one should be 2, not 31. New tabs are appended and
    the numbers rise left to right, so the rightmost is always the highest.
    """
    return numbers[-1] + 1 if numbers else 1
