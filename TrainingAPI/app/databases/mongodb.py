from pymongo import MongoClient

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
        return []
    
    def get_book_by_id(self, book_id):  
        try:
           get_book_id = self._books_col.find_one({'_id': book_id})
           if get_book_id != None:
               sach = Book()
               sach.from_dict(get_book_id)
               return sach
        except Exception as ex:
            logger.exception(ex)
        return None

    def add_book(self, book: Book):
        try:
            inserted_doc = self._books_col.insert_one(book.to_dict())
            return inserted_doc
        except Exception as ex:
            logger.exception(ex)
        return None
    
    def delete_book_by_id(self, book_id):
        try:
            delete_book_id = self._books_col.delete_one({'_id':book_id})
            return delete_book_id.deleted_count
        except Exception as ex:
            logger.exception(ex)
        return None
    
    def update_book_by_id(self, book_id, du_lieu_moi):
        try:
            du_lieu_duoc_phep = {}
            for ten_truong in ('title', 'authors', 'publisher', 'description'):
                if ten_truong in du_lieu_moi:
                    du_lieu_duoc_phep[ten_truong] = du_lieu_moi[ten_truong]

            update_book_id = self._books_col.update_one(
                {'_id': book_id},
                {'$set': du_lieu_duoc_phep}
            )
            return update_book_id.matched_count
        except Exception as ex:
            logger.exception(ex)
        return None
    
    # TODO: write functions CRUD with books
