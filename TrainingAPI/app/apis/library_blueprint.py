from sanic import Blueprint
from sanic.response import json

from app.databases.library import LibraryDB, loan_json
from app.decorators.auth import protected
from app.decorators.json_validator import validate_with_jsonschema
from app.hooks.error import ApiBadRequest


library_bp = Blueprint('library', url_prefix='')
database = LibraryDB()


@library_bp.listener('before_server_start')
async def setup_library(app, loop):
    database.ensure_indexes()


author_schema = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'name': {'type': 'string', 'pattern': r'\S', 'maxLength': 200}},
    'required': ['name']
}
borrow_schema = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'book_id': {'type': 'string', 'minLength': 1},
        'days': {'type': 'integer', 'minimum': 1, 'maximum': 30}
    }, 'required': ['book_id']
}


@library_bp.post('/authors')
@protected
@validate_with_jsonschema(jsonschema=author_schema)
async def add_author(request, username=None):
    author = database.save_author(request.json['name'])
    return json({'author': {'_id': author['_id'], 'name': author['name']}})


@library_bp.get('/authors')
async def list_authors(request):
    authors = list(database.authors.find({}, {'name_key': 0}).sort('name', 1).limit(100))
    return json({'authors': authors})


@library_bp.post('/borrows')
@protected
@validate_with_jsonschema(jsonschema=borrow_schema)
async def borrow(request, username=None):
    loan = database.borrow_book(request.json['book_id'], username, request.json.get('days', 14))
    return json({'borrow': loan_json(loan)}, status=201)


@library_bp.get('/borrows')
@protected
async def loan_history(request, username=None):
    query = {'username': username}
    status = request.args.get('status')
    if status:
        if status not in ('active', 'returned'):
            raise ApiBadRequest('status must be active or returned')
        query['status'] = status
    try:
        limit = int(request.args.get('limit', '20'))
    except ValueError:
        raise ApiBadRequest('limit must be an integer')
    if not 1 <= limit <= 100:
        raise ApiBadRequest('limit must be between 1 and 100')
    loans = database.borrows.find(query).sort('borrowed_at', -1).limit(limit)
    return json({'borrows': [loan_json(loan) for loan in loans]})


@library_bp.post('/borrows/<loan_id>/return')
@protected
async def return_loan(request, loan_id, username=None):
    return json({'borrow': loan_json(database.return_book(loan_id, username))})
