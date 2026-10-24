import uuid

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi, validate

from app.constants.cache_constants import CacheConstants
from app.databases.mongodb import MongoDB
from app.databases.redis_cached import RedisCache
from app.decorators.auth import protected
from app.decorators.json_validator import validate_with_jsonschema
from app.hooks.error import ApiInternalError
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
    # # TODO: use cache to optimize api
    # cache: RedisCache = request.app.ctx.cache
    # books = await cache.get(CacheConstants.all_books)
    # if books is None:
    #     book_objs = _db.get_books()
    #     books = [book.to_dict() for book in book_objs]
    #     await cache.set(CacheConstants.all_books, books)
    book_objs = _db.get_books()
    books = [book.to_dict() for book in book_objs]
    # books =[]
    # for book in book_objs:
    #     books.append(book.to_dict())
    number_of_books = len(books)
    return json({
        'n_books': number_of_books,
        'books': books
    }, ensure_ascii=False)

@books_bp.get('/<book_id>')
#--
async def get_one_book(request, book_id):
    one_book = _db.get_book_by_id(book_id)
    if one_book is not None:
        return json(one_book.to_dict(), status = 200, ensure_ascii = False)
    else:
        erro = {"error": "Không tìm thấy sách"}
        return json(erro, status = 404)
    
@books_bp.post('/')
# Config swagger example
@openapi.tag('Books')
@openapi.summary('Create a book')
@openapi.description('Create a book in database')
@openapi.body({'application/json': create_book_json_schema})
# -----
# Middleware for validate JWT
# @protected  # TODO: Authenticate
# -----
# Validate data from request
@validate_with_jsonschema(jsonschema=create_book_json_schema)
# -----
async def create_book(request, username=None):
    body = request.json

    book_id = str(uuid.uuid4())
    book = Book(book_id).from_dict(body)
    book.owner = username
    # # TODO: Save book to database
    inserted = _db.add_book(book)
    if not inserted:
        raise ApiInternalError('Fail to create book')

    # TODO: Update cache

    return json({'status': 'success'})

@books_bp.put('/<book_id>')
@validate_with_jsonschema(jsonschema=create_book_json_schema)
async def update_book(request, book_id):
    ket_qua = _db.update_book_by_id(book_id, request.json)
    if ket_qua is None:
        raise ApiInternalError('Fail to update book')
    if ket_qua == 0:
        return json({"error": "Không tìm thấy sách"}, status=404, ensure_ascii=False)
    return json({"message": "Đã cập nhật sách"}, status=200, ensure_ascii=False)


@books_bp.delete('/<book_id>')
async def delete_book_id(request, book_id):
    ket_qua = _db.delete_book_by_id(book_id)
    if ket_qua == 1:
        return json({"message": "Đã xóa sách"}, status = 200)
    elif ket_qua == 0:
        return json({"error": "Không tìm thấy sách"}, status = 404)
    else:
        raise ApiInternalError('Error')

# TODO: write api get, update, delete book
