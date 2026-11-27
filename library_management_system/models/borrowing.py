class BorrowTransaction:
    VALID_STATUSES = {"pending", "borrowed", "returned", "rejected", "overdue"}
    def __init__(self, transaction_id, user_id, copy_id, status="pending"):
        self.__transaction_id = transaction_id
        self.__user_id = user_id
        self.__copy_id = copy_id
        self.__status = "pending"
        self.set_status(status)
    @property
    def transaction_id(self): return self.__transaction_id
    @property
    def status(self): return self.__status
    def set_status(self, value):
        if value not in self.VALID_STATUSES:
            raise ValueError("Invalid transaction status.")
        self.__status = value
