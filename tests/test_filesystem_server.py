"""Unit tests for the bundled Filesystem MCP server tools."""

import pytest

from scp_mcp_code_agent.mcp_servers.filesystem_server import (
    create_directory,
    file_exists,
    list_directory,
    read_file,
    read_multiple_files,
    write_file,
)


class TestReadFile:
    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world", encoding="utf-8")
        assert read_file(str(f)) == "hello world"

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_file(str(tmp_path / "no_such.txt"))


class TestWriteFile:
    def test_creates_new_file(self, tmp_path):
        target = tmp_path / "out.txt"
        result = write_file(str(target), "content")
        assert target.read_text(encoding="utf-8") == "content"
        assert str(target.resolve()) in result

    def test_creates_parent_directories(self, tmp_path):
        target = tmp_path / "a" / "b" / "c.txt"
        write_file(str(target), "nested")
        assert target.read_text(encoding="utf-8") == "nested"

    def test_overwrites_existing_file(self, tmp_path):
        target = tmp_path / "f.txt"
        target.write_text("old", encoding="utf-8")
        write_file(str(target), "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_returns_char_count(self, tmp_path):
        result = write_file(str(tmp_path / "f.txt"), "abc")
        assert "3" in result


class TestListDirectory:
    def test_lists_files_and_dirs(self, tmp_path):
        (tmp_path / "b.txt").write_text("")
        (tmp_path / "a.txt").write_text("")
        (tmp_path / "sub").mkdir()
        entries = list_directory(str(tmp_path))
        assert entries == ["a.txt", "b.txt", "sub"]

    def test_returns_sorted(self, tmp_path):
        for name in ["z", "a", "m"]:
            (tmp_path / name).write_text("")
        assert list_directory(str(tmp_path)) == ["a", "m", "z"]


class TestCreateDirectory:
    def test_creates_directory(self, tmp_path):
        target = tmp_path / "new_dir"
        create_directory(str(target))
        assert target.is_dir()

    def test_creates_nested_directories(self, tmp_path):
        target = tmp_path / "a" / "b" / "c"
        create_directory(str(target))
        assert target.is_dir()

    def test_idempotent(self, tmp_path):
        target = tmp_path / "dir"
        create_directory(str(target))
        create_directory(str(target))  # should not raise
        assert target.is_dir()

    def test_returns_confirmation(self, tmp_path):
        result = create_directory(str(tmp_path / "d"))
        assert "Directory created" in result


class TestFileExists:
    def test_returns_true_for_existing_file(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("")
        assert file_exists(str(f)) is True

    def test_returns_false_for_missing_file(self, tmp_path):
        assert file_exists(str(tmp_path / "nope.txt")) is False

    def test_returns_true_for_directory(self, tmp_path):
        assert file_exists(str(tmp_path)) is True


class TestReadMultipleFiles:
    def test_reads_all_paths(self, tmp_path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("AAA", encoding="utf-8")
        b.write_text("BBB", encoding="utf-8")
        result = read_multiple_files([str(a), str(b)])
        assert result[str(a)] == "AAA"
        assert result[str(b)] == "BBB"

    def test_error_value_for_missing_file(self, tmp_path):
        missing = str(tmp_path / "gone.txt")
        result = read_multiple_files([missing])
        assert result[missing].startswith("[ERROR]")

    def test_partial_success(self, tmp_path):
        good = tmp_path / "g.txt"
        good.write_text("ok", encoding="utf-8")
        bad = str(tmp_path / "bad.txt")
        result = read_multiple_files([str(good), bad])
        assert result[str(good)] == "ok"
        assert result[bad].startswith("[ERROR]")

    def test_empty_list(self):
        assert read_multiple_files([]) == {}
