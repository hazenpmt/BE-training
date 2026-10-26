import uuid

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi, validate

from app.constants.cache_constants import CacheConstants
from app.databases.mongodb import MongoDB
from app.databases.redis_cached import RedisCache
from app.decorators.auth import protected
from app.decorators.json_validator import validate_with_jsonschema
from app.hooks.error import ApiInternalError, ApiForbidden, ApiNotFound
from app.models.book import create_book_json_schema, Book

books_bp = Blueprint('books_blueprint', url_prefix='/books')

_db = MongoDB()


@books_bp.get('/')
# Config swagger example
@openapi.tag('Books')
@openapi.summary('Get all books')
@openapi.description('Get all books from database')
# -----
async def get_all_books(request):
    cache = request.app.ctx.cache
    books = await cache.get(CacheConstants.all_books)

    if books is None:
        book_objs = _db.get_books()
        books = [book.to_dict() for book in book_objs]
        await cache.set(CacheConstants.all_books, books, expire=60)

    return json({
        'n_books': len(books),
        'books': books
    }, ensure_ascii=False)

@books_bp.get('/<book_id>')
#--
async def get_one_book(request, book_id):
    one_book = _db.get_book_by_id(book_id)
    if one_book is not None:
        return json(one_book.to_dict(), status = 200, ensure_ascii = False)
    else:
        raise ApiNotFound('Book not found')
    
@books_bp.post('/')
# Config swagger example
@openapi.tag('Books')
@openapi.summary('Create a book')
@openapi.description('Create a book in database')
@openapi.body({'application/json': create_book_json_schema})
# -----
# Middleware for validate JWT
@protected
# -----
# Validate data from request
@validate_with_jsonschema(jsonschema=create_book_json_schema)
# -----
async def create_book(request, username=None):
    body = request.json

    book_id = str(uuid.uuid4())
    book = Book(book_id).from_dict(body)
    book._id = book_id
    book.owner = username
    # # TODO: Save book to database
    inserted = _db.add_book(book)
    if not inserted:
        raise ApiInternalError('Fail to create book')

    # TODO: Update cache

    return json({'status': 'success'})

@books_bp.put('/<book_id>')
@protected
@validate_with_jsonschema(jsonschema=create_book_json_schema)
async def update_book(request, book_id, username=None):
    require_book_owner(book_id, username)
    ket_qua = _db.update_book_by_id(book_id, request.json, username)
    if ket_qua is None:
        raise ApiInternalError('Fail to update book')
    if ket_qua == 0:
        raise ApiNotFound('Book not found')
    return json({"message": "Đã cập nhật sách"}, status=200, ensure_ascii=False)


@books_bp.delete('/<book_id>')
@protected
async def delete_book_id(request, book_id, username=None):
    require_book_owner(book_id, username)
    ket_qua = _db.delete_book_by_id(book_id, username)
    if ket_qua == 1:
        return json({"message": "Đã xóa sách"}, status = 200)
    elif ket_qua == 0:
        raise ApiNotFound('Book not found')
    else:
        raise ApiInternalError('Error')

def require_book_owner(book_id, username):
    book = _db.get_book_by_id(book_id)
    if book is None:
        raise ApiNotFound('Book not found')
    if book.owner != username:
        raise ApiForbidden('Only the owner can update or delete this book')
