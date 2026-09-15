"""Root Alembic configuration."""

import logging
from logging.config import fileConfig

from alembic import config as alembic_config

# This is the Alembic Config object, which provides the values of the [alembic]
# section of the alembic.ini file as Python attributes of an Config instance.
config_obj = alembic_config.Config("alembic.ini")

# Interpret the config file for Python logging.
if config_obj.config_file_name is not None:
    fileConfig(config_obj.config_file_name)

logger = logging.getLogger("alembic.env")
