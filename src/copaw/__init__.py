# -*- coding: utf-8 -*-
import logging
import os
import time

# Compatibility fix for futu-api with protobuf >= 5.x
if "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION" not in os.environ:
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

from .constant import LOG_LEVEL_ENV
from .utils.logging import setup_logger

_t0 = time.perf_counter()
setup_logger(os.environ.get(LOG_LEVEL_ENV, "info"))
logging.getLogger(__name__).debug(
    "%.3fs package init",
    time.perf_counter() - _t0,
)
