#!/bin/sh
set -e

echo "==> Creating DB tables..."
python -c "
import os, sys
sys.path.insert(0, '/app')
from flask import Flask
from config import config
from models import db
app = Flask(__name__)
app.config.from_object(config[os.environ.get('FLASK_CONFIG', 'production')])
db.init_app(app)
with app.app_context():
    db.create_all()
    print('==> Tables ready.')
"

echo "==> Starting data import in background..."
python /app/startup.py &

echo "==> Starting Gunicorn..."
exec gunicorn --workers 4 --bind 0.0.0.0:8000 --timeout 120 \
    --env FLASK_CONFIG=production \
    run:app
