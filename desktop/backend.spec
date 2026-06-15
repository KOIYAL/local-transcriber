from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


root = Path.cwd()
datas = [(str(root / "app" / "static"), "app/static")]
datas += collect_data_files("faster_whisper")
binaries = (
    collect_dynamic_libs("av")
    + collect_dynamic_libs("ctranslate2")
    + collect_dynamic_libs("onnxruntime")
)
hiddenimports = [
    "av",
    "ctranslate2",
    "faster_whisper",
    "faster_whisper.utils",
    "huggingface_hub",
    "onnxruntime",
    "tokenizers",
]

analysis = Analysis(
    [str(root / "app" / "desktop.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="local-transcriber-backend",
    console=True,
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name="local-transcriber-backend",
)
