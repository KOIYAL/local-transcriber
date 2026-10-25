# dmgbuild settings for the macOS DMG window (used by build-macos.sh).
#
# The window shows the app on the left and an Applications shortcut on the
# right, over assets/dmg-background.png (arrow + first-launch note). dmgbuild
# writes the Finder layout directly, so it works on CI without Finder
# automation. Icon centres must match scripts/make_dmg_background.py.
#
# Usage:
#   python -m dmgbuild -s desktop/dmg-settings.py \
#     -D app=path/to/LocalTranscriber.app -D readme=START_HERE_MAC.txt \
#     -D settings_link=path/to/セキュリティ設定を開く.webloc \
#     -D background=assets/dmg-background.png "Local Transcriber" out.dmg

import os

app = defines["app"]  # noqa: F821 (provided by dmgbuild)
readme = defines["readme"]  # noqa: F821
# Opens System Settings > Privacy & Security at the Security section, where
# macOS offers "Open" for the app it just blocked.
settings_link = defines["settings_link"]  # noqa: F821
app_name = os.path.basename(app)
readme_name = os.path.basename(readme)
settings_link_name = os.path.basename(settings_link)

format = "UDZO"
filesystem = "HFS+"
files = [app, readme, settings_link]
symlinks = {"Applications": "/Applications"}
hide_extensions = [settings_link_name]

# A @2x file next to the background is combined automatically for Retina.
background = defines["background"]  # noqa: F821
# The height includes the title bar (about 32pt); the content area matches the
# 660x540 background. Without it the bottom row is cut off and scrolls.
window_rect = ((200, 120), (660, 572))
default_view = "icon-view"
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
icon_size = 100
text_size = 13
icon_locations = {
    app_name: (165, 185),
    "Applications": (495, 185),
    settings_link_name: (230, 445),
    readme_name: (430, 445),
}
