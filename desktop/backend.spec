import importlib.util
import sys
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

# Optional summary feature: bundle llama-cpp-python (and its shared
# libraries) when it is installed in the build environment.
if importlib.util.find_spec("llama_cpp") is not None:
    datas += collect_data_files("llama_cpp")
    binaries += collect_dynamic_libs("llama_cpp")
    hiddenimports += ["llama_cpp", "diskcache", "jinja2"]

# …and ship the modelshelf CLI next to the backend executable when a
# vendored copy exists (app/llm_manager.py resolves it there).
_modelshelf_name = "modelshelf.exe" if sys.platform == "win32" else "modelshelf"
_vendored_modelshelf = root / "vendor" / _modelshelf_name
if _vendored_modelshelf.exists():
    binaries += [(str(_vendored_modelshelf), ".")]

# macOS: the Apple Intelligence bridge (desktop/apple-intelligence-helper),
# resolved the same way by app/apple_intelligence.py.
_ai_helper = root / "vendor" / "apple-intelligence-helper"
if sys.platform == "darwin" and _ai_helper.exists():
    binaries += [(str(_ai_helper), ".")]

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
