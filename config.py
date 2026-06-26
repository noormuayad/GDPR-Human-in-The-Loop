import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:postgres@localhost/gdpr_audit'
    
    # Path to project data
    PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'project'))
    PRIVACY_DIR = os.path.join(PROJECT_DIR, 'privacy')
    
    # Pagination
    DOMAINS_PER_PAGE = 50
    
class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-only-insecure-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///gdpr_audit.db'

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False

    def __init__(self):
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable must be set in production.")

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
