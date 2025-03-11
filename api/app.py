""" Main Cash Lens module """
import logging
import os
import random
import sys
import threading
import time
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

import sentry_sdk
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from api.modules.parsers.models import File, Base

logging.basicConfig(
    stream=sys.stdout,
    format="%(levelname)s:%(module)s:%(funcName)s:%(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def sentry_init() -> None:  # pragma: no cover
    """Initialize sentry only if SENTRY_DSN is present"""
    if sentry_dns := os.getenv("SENTRY_DSN"):
        # Initialize Sentry SDK for error logging
        sentry_sdk.init(
            dsn=sentry_dns,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            traces_sample_rate=1.0,
            # Set profiles_sample_rate to 1.0 to profile 100%
            # of sampled transactions.
            # We recommend adjusting this value in production.
            profiles_sample_rate=1.0,
        )
        logger.info("Sentry initialized")


app = Flask("cash_lens_back")


class TimeoutMiddleware:
    def __init__(self, app_, timeout=10):
        self.app = app_
        self.timeout = timeout

    def __call__(self, environ, start_response):
        start_time = time.time()
        timeout_event = [False]  # Used to signal timeout

        def monitor_request():
            while True:
                elapsed_time = time.time() - start_time
                if elapsed_time > self.timeout:
                    timeout_event[0] = True
                    break

        # Start a monitoring thread
        monitor_thread = threading.Thread(target=monitor_request)
        monitor_thread.start()

        # Capture the response from the app
        def custom_start_response(status, headers, exc_info=None):
            if timeout_event[0]:
                # If a timeout occurred, modify the response to indicate this
                response_ = Response("Request timed out", status=504)
                return response_(environ, start_response)
            return start_response(status, headers, exc_info)

        response = self.app(environ, custom_start_response)
        return response


# Wrap the Flask app with the middleware
app.wsgi_app = TimeoutMiddleware(app.wsgi_app, timeout=10)

sentry_init()
CORS(app)
# Initialize database session
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
logger.info(f"{DATABASE_URL=}")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()
Base.metadata.create_all(engine)


@app.route("/")
def index():
    return "index.html"


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return "No file part", 400
    file = request.files["file"]
    if file.filename == "":
        return "No selected file", 400

    try:
        # Save file name to the database
        uploaded_file = File(name=file.filename, parser_name="default", progress=0)
        session.add(uploaded_file)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving file: {e}")
        return "Internal Server Error", 500
    finally:
        session.close()

    file_content = file.read().decode('latin-1')
    lines = file_content.splitlines()

    return jsonify({"file_name": file.filename, "lines": len(lines)}), 200


@app.route('/progress')
def progress():
    message = [
        "Gathering data...",
        "Analyzing trends...",
        "Calculating results...",
        "Generating report...",
        "Finalizing output..."
    ]

    # Get progress updates, potentially from a database, queue, or in-memory store
    message = random.choice(message)
    # Your function to retrieve updates
    finished = message == "Finalizing output..."

    return jsonify({"message": message, "finished": finished})
