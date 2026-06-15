from app.transcriber import TranscriptionEngine


def test_detects_cuda_runtime_errors() -> None:
    assert TranscriptionEngine._is_cuda_runtime_error(
        RuntimeError("Library cublas64_12.dll is not found")
    )
    assert TranscriptionEngine._is_cuda_runtime_error(
        RuntimeError("CUDA out of memory")
    )
    assert not TranscriptionEngine._is_cuda_runtime_error(
        RuntimeError("The media file is invalid")
    )
