"""
Run the Flask application.
"""

from app import create_app
import os

# Use FLASK_CONFIG if set, but default to production for safety
# (development config falls back to SQLite which breaks on Render)
config_name = os.getenv('FLASK_CONFIG', 'production')
app = create_app(config_name)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
