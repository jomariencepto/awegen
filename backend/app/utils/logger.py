import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(app):
    """Set up logging for the application"""
    if not app.debug and not app.testing:
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # Set up file handler
        file_handler = RotatingFileHandler(
            'logs/awegen.log',
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('AWEGen startup')


def get_logger(name):
    """Get a logger instance"""
    logger = logging.getLogger(name)
    return logger