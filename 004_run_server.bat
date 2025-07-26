@echo off
REM Set Flask app environment variable
set FLASK_APP=src\app.py

REM Run the Flask application in debug mode
echo Running Flask server... (Press Ctrl+C to stop)
flask run --debug
