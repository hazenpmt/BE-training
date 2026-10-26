"""Run reproducible explain checks in a disposable, isolated MongoDB database."""
import datetime
import json
import os
import uuid

from dotenv import load_dotenv

load_dotenv()
database_name = 'training_module2_check_' + uuid.uuid4().hex
os.environ['MONGO_DATABASE'] = database_name

from app.databases.library import LibraryDB


def explain(database, collection, query, sort=None):
    command = {'find': collection, 'filter': query}
    if sort:
        command['sort'] = sort
    result = database.command('explain', command, verbosity='executionStats')
    stats = result['executionStats']
    return {
        'returned': stats['nReturned'],
        'documents_examined': stats['totalDocsExamined'],
        'keys_examined': stats['totalKeysExamined'],
        'winning_plan': result['queryPlanner']['winningPlan']
    }


def main():
    library = LibraryDB()
    assert library.db.name == database_name
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        library._books_col.insert_many([
            {'_id': str(i), 'title': 'Book ' + str(i), 'author_ids': ['author-' + str(i % 100)]}
            for i in range(1000)
        ])
        library.borrows.insert_many([
            {'_id': str(i), 'book_id': str(i), 'username': 'user-' + str(i % 100),
             'status': 'returned', 'borrowed_at': now - datetime.timedelta(minutes=i)}
            for i in range(1000)
        ])
        queries = [('books', {'author_ids': 'author-7'}, None),
                   ('borrows', {'username': 'user-7', 'status': 'returned'}, {'borrowed_at': -1})]
        before = [explain(library.db, *query) for query in queries]
        library.ensure_indexes()
        after = [explain(library.db, *query) for query in queries]
        for old, new in zip(before, after):
            assert old['returned'] == new['returned'] == 10
            assert new['documents_examined'] < old['documents_examined']
            assert new['keys_examined'] > 0
        print(json.dumps({'before': before, 'after': after}, indent=2, default=str))
    finally:
        library.client.drop_database(database_name)
        library.client.close()


if __name__ == '__main__':
    main()
