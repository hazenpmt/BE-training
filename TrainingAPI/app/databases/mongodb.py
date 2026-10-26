from pymongo import MongoClient
import datetime
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.hooks.error import ApiInternalError

from app.constants.mongodb_constants import MongoCollections
from app.models.book import Book
from app.utils.logger_utils import get_logger
from config import MongoDBConfig

logger = get_logger('MongoDB')


class MongoDB:
    def __init__(self, connection_url=None):
        if connection_url is None:
            connection_url = MongoDBConfig.CONNECTION_URL

        self.connection_url = connection_url.split('@')[-1]
        self.client = MongoClient(connection_url)
        self.db = self.client[MongoDBConfig.DATABASE]

        self._books_col = self.db[MongoCollections.books]
        self._users_col = self.db[MongoCollections.users]
        self._sessions_col = self.db['auth_sessions']

    def get_books(self, filter_=None, projection=None):
        try:
            if not filter_:
                filter_ = {}
            cursor = self._books_col.find(filter_, projection=projection)
            data = []
            for doc in cursor:
                data.append(Book().from_dict(doc))
            return data
        except Exception as ex:
            logger.exception(ex)
            raise ApiInternalError('Fail to get books') from ex
    
    def get_book_by_id(self, book_id):  
        try:
           get_book_id = self._books_col.find_one({'_id': book_id})
           if get_book_id != None:
               sach = Book()
               sach.from_dict(get_book_id)
               return sach
        except Exception as ex:
            logger.exception(ex)
            raise ApiInternalError('Fail to get book') from ex

    def add_book(self, book: Book):
        try:
            inserted_doc = self._books_col.insert_one(book.to_dict())
            return inserted_doc
        except Exception as ex:
            logger.exception(ex)
        return None
    
    def delete_book_by_id(self, book_id, username):
        try:
            delete_book_id = self._books_col.delete_one(
                {'_id': book_id, 'owner': username}
            )
            return delete_book_id.deleted_count
        except Exception as ex:
            logger.exception(ex)
        return None
    
    def update_book_by_id(self, book_id, du_lieu_moi, username):
        try:
            du_lieu_duoc_phep = {}
            for ten_truong in ('title', 'authors', 'author_ids', 'publisher', 'description'):
                if ten_truong in du_lieu_moi:
                    du_lieu_duoc_phep[ten_truong] = du_lieu_moi[ten_truong]

            update_book_id = self._books_col.update_one(
                {'_id': book_id, 'owner': username},
                {'$set': du_lieu_duoc_phep}
            )
            return update_book_id.matched_count
        except Exception as ex:
            logger.exception(ex)
        return None
    
    # TODO: write functions CRUD with books

    def add_user(self, username, password_hash):
        try:
            self._users_col.insert_one({
                '_id': username,
                'username': username,
                'password_hash': password_hash,
                'role': 'user'
            })
            return True
        except DuplicateKeyError:
            return False
        except PyMongoError as ex:
            logger.exception(ex)
            raise ApiInternalError('Fail to create user') from ex

    def get_user_by_username(self, username):
        try:
            return self._users_col.find_one({'_id': username})
        except PyMongoError as ex:
            logger.exception(ex)
            raise ApiInternalError('Fail to get user') from ex

    def ensure_session_index(self):
        self._sessions_col.create_index('expires_at', expireAfterSeconds=0)

    def save_session(self, session_id, username, access, refresh):
        self._sessions_col.insert_one({
            '_id': session_id, 'username': username, 'active': True,
            'access_jti': access['jti'], 'refresh_jti': refresh['jti'],
            'expires_at': datetime.datetime.fromtimestamp(refresh['exp'], datetime.timezone.utc)
        })

    def get_session(self, session_id):
        return self._sessions_col.find_one({'_id': session_id, 'active': True})

    def rotate_session(self, old, access, refresh):
        result = self._sessions_col.update_one(
            {'_id': old['sid'], 'username': old['username'],
             'active': True, 'refresh_jti': old['jti']},
            {'$set': {'access_jti': access['jti'], 'refresh_jti': refresh['jti'],
                      'expires_at': datetime.datetime.fromtimestamp(refresh['exp'], datetime.timezone.utc)}}
        )
        return result.matched_count == 1

    def revoke_session(self, session_id, username):
        self._sessions_col.update_one(
            {'_id': session_id, 'username': username}, {'$set': {'active': False}}
        )

    def list_users(self):
        return list(self._users_col.find({}, {'_id': 0, 'username': 1, 'role': 1}).limit(100))
