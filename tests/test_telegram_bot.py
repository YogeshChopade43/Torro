from torro.telegram_bot import is_owner, split_message


def test_split_respects_limit_and_keeps_text():
    text = ("line\n" * 2000) + "x" * 5000
    parts = split_message(text, 4096)
    assert all(len(p) <= 4096 for p in parts)
    assert "".join(parts).replace("\n", "") == text.replace("\n", "")


def test_short_message_single_part():
    assert split_message("hi") == ["hi"]


def test_only_owner():
    assert is_owner(42, 42) and not is_owner(7, 42) and not is_owner(None, 42)
