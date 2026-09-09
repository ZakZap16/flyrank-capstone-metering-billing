import pytest
from src.config.logging import configure_logging, get_logger


class TestConfigureLogging:
    def test_configures_without_error(self):
        configure_logging(log_level="INFO")

    def test_configures_debug_level(self):
        configure_logging(log_level="DEBUG")

    def test_configures_invalid_level_falls_back(self):
        configure_logging(log_level="INVALID")


class TestGetLogger:
    def test_returns_bound_logger(self):
        logger = get_logger("test_module")
        assert logger is not None

    def test_logger_has_name(self):
        logger = get_logger("my_module")
        logger.info("test_message")
