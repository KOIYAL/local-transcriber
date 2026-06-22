from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


FOUNDATION = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"
UAP = "http://schemas.microsoft.com/appx/manifest/uap/windows10"
UAP2 = "http://schemas.microsoft.com/appx/manifest/uap/windows10/2"
UAP3 = "http://schemas.microsoft.com/appx/manifest/uap/windows10/3"
UAP10 = "http://schemas.microsoft.com/appx/manifest/uap/windows10/10"
DESKTOP = "http://schemas.microsoft.com/appx/manifest/desktop/windows10"
DESKTOP6 = "http://schemas.microsoft.com/appx/manifest/desktop/windows10/6"
RESCAP = (
    "http://schemas.microsoft.com/appx/manifest/"
    "foundation/windows10/restrictedcapabilities"
)

NAMESPACES = {
    "": FOUNDATION,
    "uap": UAP,
    "uap2": UAP2,
    "uap3": UAP3,
    "uap10": UAP10,
    "desktop": DESKTOP,
    "desktop6": DESKTOP6,
    "rescap": RESCAP,
}

TILE_ASSETS = {
    "store_logo": r"Assets\StoreLogo.png",
    "square44": r"Assets\Square44x44Logo.png",
    "square71": r"Assets\Square71x71Logo.png",
    "square150": r"Assets\Square150x150Logo.png",
    "square310": r"Assets\Square310x310Logo.png",
    "wide310": r"Assets\Wide310x150Logo.png",
    "splash": r"Assets\SplashScreen.png",
}

for prefix, namespace in NAMESPACES.items():
    ET.register_namespace(prefix, namespace)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"{name} is required. Copy the exact value from "
            "Partner Center > Product management > Product identity."
        )
    return value


def child(parent: ET.Element, tag: str) -> ET.Element:
    element = parent.find(tag)
    if element is None:
        raise ValueError(f"Manifest element not found: {tag}")
    return element


def child_or_create(parent: ET.Element, tag: str) -> ET.Element:
    element = parent.find(tag)
    return element if element is not None else ET.SubElement(parent, tag)


def child_or_insert_before(
    parent: ET.Element,
    tag: str,
    before_tag: str,
) -> ET.Element:
    element = parent.find(tag)
    if element is not None:
        return element

    element = ET.Element(tag)
    for index, sibling in enumerate(parent):
        if sibling.tag == before_tag:
            parent.insert(index, element)
            return element
    parent.append(element)
    return element


def verify_tile_assets(manifest_path: Path) -> None:
    missing = [
        relative_path
        for relative_path in TILE_ASSETS.values()
        if not (manifest_path.parent / relative_path.replace("\\", "/")).is_file()
    ]
    if missing:
        raise ValueError(
            "MSIX tile assets are missing: "
            + ", ".join(missing)
            + ". Run package-msix.cmd from the project root."
        )


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: prepare_store_manifest.py <Package.appxmanifest>")
        return 2

    manifest_path = Path(sys.argv[1])
    verify_tile_assets(manifest_path)
    identity_name = required_env("STORE_IDENTITY_NAME")
    publisher = required_env("STORE_PUBLISHER")
    publisher_display_name = os.getenv(
        "STORE_PUBLISHER_DISPLAY_NAME",
        "株式会社KOIYAL",
    ).strip()
    display_name = os.getenv(
        "STORE_DISPLAY_NAME",
        "文字起こし - 買い切りのみのサブスクなし",
    ).strip()
    description = os.getenv(
        "STORE_DESCRIPTION",
        "音声・動画ファイルをPC上で文字起こしする買い切り型Windowsアプリ",
    ).strip()
    version = os.getenv("STORE_PACKAGE_VERSION", "1.0.2.0").strip()

    tree = ET.parse(manifest_path)
    root = tree.getroot()
    root.set("IgnorableNamespaces", "uap uap10 rescap")
    identity = child(root, f"{{{FOUNDATION}}}Identity")
    properties = child(root, f"{{{FOUNDATION}}}Properties")
    application = child(
        child(root, f"{{{FOUNDATION}}}Applications"),
        f"{{{FOUNDATION}}}Application",
    )
    visual_elements = child(application, f"{{{UAP}}}VisualElements")
    resources = child(root, f"{{{FOUNDATION}}}Resources")

    identity.set("Name", identity_name)
    identity.set("Publisher", publisher)
    identity.set("Version", version)
    child(properties, f"{{{FOUNDATION}}}DisplayName").text = display_name
    child(properties, f"{{{FOUNDATION}}}PublisherDisplayName").text = (
        publisher_display_name
    )
    child(properties, f"{{{FOUNDATION}}}Logo").text = TILE_ASSETS["store_logo"]
    visual_elements.set("DisplayName", display_name)
    short_name = os.getenv("STORE_SHORT_NAME", "文字起こし").strip() or "文字起こし"
    visual_elements.set("ShortName", short_name)
    visual_elements.set("Description", description)
    visual_elements.set("BackgroundColor", "#153F31")
    visual_elements.set("Square44x44Logo", TILE_ASSETS["square44"])
    visual_elements.set("Square150x150Logo", TILE_ASSETS["square150"])

    default_tile = child_or_insert_before(
        visual_elements,
        f"{{{UAP}}}DefaultTile",
        f"{{{UAP}}}SplashScreen",
    )
    default_tile.set("Square71x71Logo", TILE_ASSETS["square71"])
    default_tile.set("Square310x310Logo", TILE_ASSETS["square310"])
    default_tile.set("Wide310x150Logo", TILE_ASSETS["wide310"])
    default_tile.set("ShowNameOnSquare150x150Logo", "false")
    default_tile.set("ShowNameOnSquare310x310Logo", "false")
    default_tile.set("ShowNameOnWide310x150Logo", "false")

    splash_screen = child_or_create(visual_elements, f"{{{UAP}}}SplashScreen")
    splash_screen.set("Image", TILE_ASSETS["splash"])
    splash_screen.set("BackgroundColor", "#153F31")

    for resource in list(resources):
        resources.remove(resource)
    ET.SubElement(resources, f"{{{FOUNDATION}}}Resource", Language="ja-jp")
    ET.SubElement(resources, f"{{{FOUNDATION}}}Resource", Language="en-us")

    ET.indent(tree, space="  ")
    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
    print("Store manifest prepared:")
    print(f"  Identity Name: {identity_name}")
    print(f"  Publisher: {publisher}")
    print(f"  PublisherDisplayName: {publisher_display_name}")
    print(f"  DisplayName: {display_name}")
    print(f"  Version: {version}")
    print("  Tile assets: custom Local Transcriber logos")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
