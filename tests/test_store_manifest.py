from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "desktop" / "prepare_store_manifest.py"
SPEC = importlib.util.spec_from_file_location("prepare_store_manifest", MODULE_PATH)
assert SPEC and SPEC.loader
store_manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(store_manifest)


def test_prepare_store_manifest_uses_custom_tile_assets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for relative_path in store_manifest.TILE_ASSETS.values():
        asset_path = tmp_path / relative_path.replace("\\", "/")
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(b"png")

    manifest_path = tmp_path / "Package.appxmanifest"
    manifest_path.write_text(
        f'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="{store_manifest.FOUNDATION}" xmlns:uap="{store_manifest.UAP}">
  <Identity Name="default" Publisher="CN=default" Version="1.0.0.0" />
  <Properties>
    <DisplayName>Default</DisplayName>
    <PublisherDisplayName>Default</PublisherDisplayName>
    <Logo>Assets\\Default.png</Logo>
  </Properties>
  <Resources>
    <Resource Language="en-us" />
  </Resources>
  <Applications>
    <Application Id="App" Executable="LocalTranscriber.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="Default" Description="Default" BackgroundColor="#000000"
        Square150x150Logo="Assets\\Default150.png" Square44x44Logo="Assets\\Default44.png">
        <uap:SplashScreen Image="Assets\\DefaultSplash.png" />
      </uap:VisualElements>
    </Application>
  </Applications>
</Package>''',
        encoding="utf-8",
    )

    monkeypatch.setenv("STORE_IDENTITY_NAME", "StoreIdentity")
    monkeypatch.setenv("STORE_PUBLISHER", "CN=KOIYAL")
    monkeypatch.setattr(sys, "argv", ["prepare_store_manifest.py", str(manifest_path)])

    assert store_manifest.main() == 0

    root = ET.parse(manifest_path).getroot()
    properties = root.find(f"{{{store_manifest.FOUNDATION}}}Properties")
    visual_elements = root.find(
        f"{{{store_manifest.FOUNDATION}}}Applications/"
        f"{{{store_manifest.FOUNDATION}}}Application/"
        f"{{{store_manifest.UAP}}}VisualElements"
    )
    assert properties is not None
    assert visual_elements is not None
    assert properties.findtext(f"{{{store_manifest.FOUNDATION}}}Logo") == store_manifest.TILE_ASSETS[
        "store_logo"
    ]
    assert visual_elements.get("Square44x44Logo") == store_manifest.TILE_ASSETS["square44"]
    assert visual_elements.get("Square150x150Logo") == store_manifest.TILE_ASSETS["square150"]
    assert visual_elements.get("BackgroundColor") == "#153F31"

    default_tile = visual_elements.find(f"{{{store_manifest.UAP}}}DefaultTile")
    splash_screen = visual_elements.find(f"{{{store_manifest.UAP}}}SplashScreen")
    assert default_tile is not None
    assert splash_screen is not None
    assert default_tile.get("Square71x71Logo") == store_manifest.TILE_ASSETS["square71"]
    assert default_tile.get("Square310x310Logo") == store_manifest.TILE_ASSETS["square310"]
    assert default_tile.get("Wide310x150Logo") == store_manifest.TILE_ASSETS["wide310"]
    assert splash_screen.get("Image") == store_manifest.TILE_ASSETS["splash"]
    assert list(visual_elements).index(default_tile) < list(visual_elements).index(splash_screen)
