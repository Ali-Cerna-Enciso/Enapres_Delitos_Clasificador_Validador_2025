#!/usr/bin/env python3
"""
Módulo de Logging Estructurado
Proporciona logging consistente para todo el proyecto
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Formatter con colores para consola"""

    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }

    def format(self, record):
        if sys.stdout.isatty():  # Solo colorear si es terminal interactivo
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logger(
    name: str,
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    console_output: bool = True
) -> logging.Logger:
    """Configura logger con salida a consola y archivo opcional"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = ColoredFormatter(log_format, datefmt=date_format)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_default_log_file(script_name: str) -> Path:
    """Genera ruta de log por defecto (logs/<script>_YYYYMMDD.log)"""
    project_root = Path(__file__).resolve().parents[2]
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = logs_dir / f"{script_name}_{timestamp}.log"

    return log_file


def get_project_logger(name: str = "enapres_validator") -> logging.Logger:
    """Obtiene logger principal del proyecto"""
    log_file = get_default_log_file("project")
    return setup_logger(name, log_file=log_file, level=logging.INFO)


if __name__ == "__main__":
    logger = get_project_logger("test_module")
    logger.debug("Esto es un mensaje DEBUG")
    logger.info("Esto es un mensaje INFO")
    logger.warning("Esto es un mensaje WARNING")
    logger.error("Esto es un mensaje ERROR")
    logger.critical("Esto es un mensaje CRITICAL")

    # Logger personalizado
    custom_log = Path("logs/custom_test.log")
    custom_logger = setup_logger("custom", log_file=custom_log, level=logging.DEBUG)
    custom_logger.info("Logger personalizado funcionando")
