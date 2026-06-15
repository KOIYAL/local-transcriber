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


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: prepare_store_manifest.py <Package.appxmanifest>")
        return 2

    manifest_path = Path(sys.argv[1])
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
    version = os.getenv("STORE_PACKAGE_VERSION", "1.0.1.0").strip()

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
    visual_elements.set("DisplayName", display_name)
    visual_elements.set("Description", description)

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
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
