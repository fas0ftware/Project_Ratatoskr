import unittest

import main


class ParseArgsTests(unittest.TestCase):
    def test_defaults(self):
        args = main.parse_args(["Alice", "hello"])
        self.assertEqual((args.contact, args.message, args.repeat, args.login_wait), ("Alice", "hello", 1, 30))

    def test_repeat_is_limited(self):
        for bad in ("0", "-1", str(main.MAX_REPEAT + 1)):
            with self.assertRaises(SystemExit):
                main.parse_args(["Alice", "hi", "-n", bad])
        self.assertEqual(main.parse_args(["Alice", "hi", "-n", str(main.MAX_REPEAT)]).repeat, main.MAX_REPEAT)

    def test_empty_values_are_rejected(self):
        with self.assertRaises(SystemExit):
            main.parse_args(["Alice", "   "])
        with self.assertRaises(SystemExit):
            main.parse_args(["  ", "hi"])

    def test_profile_dir_from_environment(self):
        self.assertEqual(main.default_profile_dir({"RATATOSKR_PROFILE": "/x"}), "/x")
        self.assertEqual(main.default_profile_dir({}), main.DEFAULT_PROFILE)

    def test_importing_main_does_not_send_anything(self):
        # importing must have no side effects (it used to send messages on import)
        self.assertTrue(callable(main.send_whatsapp))


if __name__ == "__main__":
    unittest.main()
