import base64
import mimetypes
import os
import sublime
import time
from .log import msg


def get_package_name() -> str:
    return __package__


def get_package_path() -> str:
    return "Packages/" + get_package_name()


def get_image_path(img_name: str) -> str:
    img_path = get_setting("image_" + img_name)

    assert isinstance(img_path, str)

    return sublime.expand_variables(
        img_path,
        {
            # fmt: off
            "package": get_package_name(),
            "package_path": get_package_path(),
            # fmt: on
        },
    )


def get_image_info(img_name: str) -> dict:
    img_path = get_image_path(img_name)
    img_ext = os.path.splitext(img_path)[1]

    try:
        img_base64 = base64.b64encode(sublime.load_binary_resource(img_path)).decode()
    except IOError:
        img_base64 = ""
        print(msg("Resource not found: " + img_path))

    img_mime = mimetypes.types_map.get(img_ext, "")

    if not img_mime:
        print(msg("Cannot determine MIME type: " + img_path))

    img_data_uri = "data:{mime};base64,{base64}".format(mime=img_mime, base64=img_base64)

    # fmt: off
    return {
        "base64": img_base64,
        "data_uri": img_data_uri,
        "mime": img_mime,
        "path": img_path,
    }
    # fmt: on


def get_settings_file() -> str:
    """
    hard-coded workaround for different package name
    due to installation via Package Control: Add Repository
    """

    return "OpenUriInBrowser.sublime-settings"


def get_settings_object() -> sublime.Settings:
    return sublime.load_settings(get_settings_file())


def get_setting(key: str, default=None):
    return get_settings_object().get(key, default)


def get_timestamp() -> float:
    return time.time()
