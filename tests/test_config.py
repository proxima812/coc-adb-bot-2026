from __future__ import annotations

import dataclasses
import unittest

from coc_bot.config import BotConfig, RelativePoint, _config_from_dict, validate_config


class ConfigValidationTest(unittest.TestCase):
    def test_validate_config_rejects_non_ldplayer_emulator_type(self) -> None:
        config = dataclasses.replace(BotConfig(), emulator_type="bluestacks")

        with self.assertRaisesRegex(ValueError, "emulator_type must be ldplayer, got bluestacks"):
            validate_config(config)

    def test_validate_config_rejects_empty_fallback_deploy_points(self) -> None:
        config = dataclasses.replace(BotConfig(), fallback_deploy_points=[])

        with self.assertRaisesRegex(ValueError, "fallback_deploy_points should contain at least one G point"):
            validate_config(config)

    def test_config_from_dict_reports_unknown_extra_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown bot config key\\(s\\): unexpected_setting"):
            _config_from_dict({"unexpected_setting": True})


if __name__ == "__main__":
    unittest.main()
