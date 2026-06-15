from __future__ import annotations

import unittest


class MainEntrypointTest(unittest.TestCase):
    def test_cli_parse_args_is_available_without_runtime_startup(self) -> None:
        from coc_bot.cli import parse_args

        args = parse_args(["--bot-mode", "builder", "--max-attacks", "3"])

        self.assertEqual(args.bot_mode, "builder")
        self.assertEqual(args.max_attacks, 3)

    def test_main_exports_runner_loops_for_compatibility(self) -> None:
        from coc_bot import main
        from coc_bot import runner

        self.assertIs(main.run_home_loop, runner.run_home_loop)
        self.assertIs(main.run_builder_loop, runner.run_builder_loop)


if __name__ == "__main__":
    unittest.main()
