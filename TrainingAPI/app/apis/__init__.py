from sanic import Blueprint

from app.apis.books_blueprint import books_bp
from app.apis.auth_blueprint import auth_bp
from app.apis.library_blueprint import library_bp
from app.apis.example_blueprint import example

api = Blueprint.group(example, books_bp, auth_bp, library_bp, version=1)
