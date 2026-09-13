import pytest
from src.config.logging import configure_logging


class TestConfigureLogging:
    def test_configures_without_error(self):
        configure_logging(log_level="INFO")

    def test_configures_debug_level(self):
        configure_logging(log_level="DEBUG")

    def test_configures_invalid_level_falls_back(self):
        configure_logging(log_level="INVALID")
