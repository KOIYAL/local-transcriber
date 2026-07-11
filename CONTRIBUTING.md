# Contributing to Local Transcriber

Thanks for your interest! Issues and pull requests are welcome **in English
or Japanese**（日本語で大丈夫です）.

## Setup

```console
$ python -m venv .venv
$ .venv/bin/pip install -e ".[dev]"
$ .venv/bin/python -m pytest
```

Tests run without network access, real models, or the modelshelf binary —
external processes are faked (see `tests/test_llm_manager.py` for the
pattern). Please keep it that way: any new integration needs an injectable
seam and a fake in its tests.

## Guidelines

- Add or update tests for any behavior change; `pytest` must pass.
- Match the style of the surrounding code; keep the UI bilingual — new
  user-facing strings go into both locales in `app/static/app.js`.
- The summary feature must stay strictly optional: without the modelshelf
  binary or the `summary` extra installed, the app behaves exactly like a
  build without the feature.
- Larger changes: please open an issue first to discuss the direction.

## License of contributions

By submitting a contribution you agree that it is licensed under the
project's [AGPL-3.0](LICENSE) license.
