from typing import Generator

import sublime

from .functions import is_view_too_large, is_view_typing, view_is_dirty_val
from .logger import log
from .phantom_set import erase_phantom_set, update_phantom_set
from .region_drawing import draw_uri_regions, erase_uri_regions
from .settings import get_setting, get_setting_show_open_button
from .shared import global_get
from .timer import RepeatingTimer
from .utils import is_processable_view, is_transient_view, view_find_all


def foreground_views() -> Generator[sublime.View, None, None]:
    for window in sublime.windows():
        for group_idx in range(window.num_groups()):
            if view := window.active_view_in_group(group_idx):
                yield view


class RendererThread(RepeatingTimer):
    def __init__(self, interval_ms: int = 1000) -> None:
        super().__init__(interval_ms, self._update_foreground_views)

        # to prevent from overlapped processes when using a low interval
        self.is_rendering = False

    def _update_foreground_views(self) -> None:
        if self.is_rendering:
            return

        self.is_rendering = True
        for view in foreground_views():
            self._update_view(view)
        self.is_rendering = False

    def _update_view(self, view: sublime.View) -> None:
        if (
            not is_processable_view(view)
            or not view_is_dirty_val(view)
            or is_view_typing(view)
            or (is_transient_view(view) and not get_setting("work_for_transient_view"))
        ):
            return

        if is_view_too_large(view):
            self._clean_up_phantom_set(view)
            self._clean_up_uri_regions(view)
            view_is_dirty_val(view, False)
            return

        self._detect_uris_globally(view)
        view_is_dirty_val(view, False)

    def _detect_uris_globally(self, view: sublime.View) -> None:
        uri_regions = tuple(
            view_find_all(
                view,
                global_get("uri_regex_obj"),
                get_setting("expand_uri_regions_selectors"),
            )
        )

        # handle Phantoms
        if get_setting_show_open_button(view) == "always":
            update_phantom_set(view, uri_regions)
            log("debug_low", "re-render phantoms")
        else:
            self._clean_up_phantom_set(view)

        # handle draw URI regions
        if get_setting("draw_uri_regions.enabled") == "always":
            draw_uri_regions(view, uri_regions)
            log("debug_low", "draw URI regions")
        else:
            self._clean_up_uri_regions(view)

    def _clean_up_phantom_set(self, view: sublime.View) -> None:
        erase_phantom_set(view)
        log("debug_low", "erase phantoms")

    def _clean_up_uri_regions(self, view: sublime.View) -> None:
        erase_uri_regions(view)
        log("debug_low", "erase URI regions")
