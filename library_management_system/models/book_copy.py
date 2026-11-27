class BookCopy:
    VALID_STATUSES = {"available", "requested", "borrowed", "reserved", "maintenance"}
    def __init__(self, copy_id, book_id, accession_number, status="available"):
        self.__copy_id = copy_id
        self.__book_id = book_id
        self.__accession_number = str(accession_number).strip()
        self.__status = "available"
        self.set_status(status)
    @property
    def accession_number(self): return self.__accession_number
    @property
    def status(self): return self.__status
    def set_status(self, value):
        if value not in self.VALID_STATUSES:
            raise ValueError("Invalid copy status.")
        self.__status = value
