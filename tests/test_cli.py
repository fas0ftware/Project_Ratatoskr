import datetime as dt
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import main


class ParseArgsTests(unittest.TestCase):
    def test_defaults(self):
        args = main.parse_args(["Alice", "hello"])
        self.assertEqual((args.contacts, args.text, args.repeat, args.send_at), (["Alice"], "hello", 1, None))

    def test_several_recipients_without_duplicates(self):
        args = main.parse_args(["--to", "Alice", "--to", "Family", "--to", "Alice", "hello all"])
        self.assertEqual((args.contacts, args.text), (["Alice", "Family"], "hello all"))

    def test_total_messages_are_capped(self):
        self.assertEqual(main.parse_args(["Alice", "hi", "-n", str(main.MAX_TOTAL)]).repeat, main.MAX_TOTAL)
        bad = [["Alice", "hi", "-n", "0"], ["Alice", "hi", "-n", str(main.MAX_TOTAL + 1)],
               ["--to", "A", "--to", "B", "--to", "C", "hi", "-n", "7"]]
        for argv in bad:
            with self.assertRaises(SystemExit), mock.patch("sys.stderr", io.StringIO()):
                main.parse_args(argv)

    def test_validation(self):
        for argv in (["Alice", "   "], ["  ", "hi"], ["Alice", "x" * (main.MAX_LENGTH + 1)],
                     ["Alice", "hi", "--delay", "0.2"], ["Alice", "hi", "--at", "25:99"],
                     ["Alice", "hi", "--login-wait", "1"], ["Alice", "--file", "/nope/missing.txt"]):
            with self.assertRaises(SystemExit), mock.patch("sys.stderr", io.StringIO()):
                main.parse_args(argv)

    def test_stdin_and_file(self):
        with mock.patch("sys.stdin", io.StringIO("line 1\nline 2\n")):
            self.assertEqual(main.parse_args(["Alice", "-"]).text, "line 1\nline 2")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
            fh.write("  from a file 🚀 \n")
        self.addCleanup(os.remove, fh.name)
        self.assertEqual(main.parse_args(["Alice", "--file", fh.name]).text, "from a file 🚀")

    def test_parse_at(self):
        now = dt.datetime(2026, 11, 11, 21, 0)
        self.assertEqual(main.parse_at("21:30", now), dt.datetime(2026, 11, 11, 21, 30))
        self.assertEqual(main.parse_at("08:00", now), dt.datetime(2026, 11, 12, 8, 0))
        with self.assertRaises(ValueError):
            main.parse_at("soon", now)

    def test_profile_dir_from_environment(self):
        self.assertEqual(main.default_profile_dir({"RATATOSKR_PROFILE": "/x"}), "/x")
        self.assertEqual(main.default_profile_dir({}), main.DEFAULT_PROFILE)

    def test_dry_run_opens_no_browser(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main.main(["--to", "Alice", "--to", "Bob", "two\nlines", "--dry-run"]), 0)
        self.assertEqual(out.getvalue().count("would send"), 2)
        self.assertIn("  | lines", out.getvalue())


class Keys:
    CONTROL, SHIFT, ENTER, BACKSPACE = "<CTRL>", "<SHIFT>", "<ENTER>", "<BS>"


class Element:
    def __init__(self, log, name):
        self.log, self.name = log, name

    def click(self):
        self.log.append((self.name, "click"))

    def send_keys(self, text):
        self.log.append((self.name, text))


class Driver:
    def __init__(self, log):
        self.log = log

    def execute_script(self, script, element, text):
        self.log.append((element.name, f"insert:{text}"))


class WhatsAppFlowTests(unittest.TestCase):
    def setUp(self):
        self.log = []
        elements = {main.SEARCH_BOX: Element(self.log, "search"), main.MESSAGE_BOX: Element(self.log, "box")}
        self.app = main.WhatsApp(Driver(self.log), elements.__getitem__, Keys, sleep=lambda s: None)

    def test_send_opens_chat_and_sends_each_copy(self):
        self.assertEqual(self.app.send("Alice", "hi", repeat=2, delay=1), 2)
        typed = [t for who, t in self.log if who == "search" and t != "click"]
        self.assertEqual(typed, ["<CTRL>a", "<BS>", "Alice", "<ENTER>"])
        self.assertEqual([t for who, t in self.log if who == "box"].count("<ENTER>"), 2)

    def test_multiline_uses_shift_enter(self):
        self.app.type_message(Element(self.log, "box"), "one\n\nthree")
        self.assertEqual([t for _, t in self.log], ["one", "<SHIFT><ENTER>", "<SHIFT><ENTER>", "three"])

    def test_emoji_lines_are_inserted_not_typed(self):
        self.app.type_message(Element(self.log, "box"), "plain\nrocket 🚀")
        self.assertIn(("box", "insert:rocket 🚀"), self.log)
        self.assertIn(("box", "plain"), self.log)


if __name__ == "__main__":
    unittest.main()
