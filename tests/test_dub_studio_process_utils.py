import builtins

from tools.dub_studio.process_utils import emit, safe_print


def test_safe_print_ignores_broken_pipe(monkeypatch):
    def broken_print(*args, **kwargs):
        raise BrokenPipeError("pipe closed")

    monkeypatch.setattr(builtins, "print", broken_print)
    safe_print("hello", flush=True)


def test_emit_falls_back_to_ascii_when_stdout_encoding_breaks(monkeypatch):
    calls: list[str] = []

    def flaky_print(*args, **kwargs):
        message = str(args[0]) if args else ""
        calls.append(message)
        if len(calls) == 1:
            raise UnicodeEncodeError("cp1252", "Đ", 0, 1, "bad encode")

    monkeypatch.setattr(builtins, "print", flaky_print)
    emit("PROGRESS", {"message": "Đang chạy"})

    assert len(calls) == 2
    assert calls[0] != calls[1]
    assert "\\u0110ang ch\\u1ea1y" in calls[1]
