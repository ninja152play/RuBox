import sys
from loguru import logger


def init_logger(path):
    logger.remove()

    logger.add(
        sys.stdout,
        format='{time:YYYY-MM-DD HH:mm:ss} | <lvl>{level: <8} </lvl> | {message}',
        level='INFO',
        colorize=True
    )

    logger.add(
        path,
        format='{time:YYYY-MM-DD HH:mm:ss} | <lvl>{level: <8} </lvl> | {message}',
        level='INFO',
        rotation='10 MB',
        retention='14 days'
    )
