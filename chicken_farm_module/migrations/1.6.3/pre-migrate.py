# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pre-migration script for chicken_farm_module v1.6.3:
    Logs upgrade start from v1.6.2 -> v1.6.3.
    """
    _logger.info("===========================================================")
    _logger.info("[chicken_farm_module] Starting Pre-Migration to v1.6.3...")
    _logger.info("[chicken_farm_module] Installed DB Version: %s", version)
    _logger.info("===========================================================")
