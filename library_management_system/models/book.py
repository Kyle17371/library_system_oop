class Book:
    def __init__(self, book_id, title, isbn=None, publisher=None, publication_year=None):
        self.__book_id = book_id
        self.__title = ""
        self.__isbn = None
        self.__publisher = publisher
        self.__publication_year = publication_year
        self.set_title(title)
        self.set_isbn(isbn)

    @property
    def book_id(self): return self.__book_id
    @property
    def title(self): return self.__title
    @property
    def isbn(self): return self.__isbn

    def set_title(self, value):
        value = str(value).strip()
        if not value: raise ValueError("Book title is required.")
        self.__title = value

    def set_isbn(self, value):
        self.__isbn = str(value).strip() if value else None
