from abc import ABC, abstractmethod

class LibraryUser(ABC):
    def __init__(self, user_id, username, full_name, email, department=""):
        self.__user_id = int(user_id)
        self.__username = username
        self.__full_name = full_name
        self.__email = email
        self._department = department or ""

    @property
    def user_id(self): return self.__user_id
    @property
    def username(self): return self.__username
    @property
    def full_name(self): return self.__full_name
    @property
    def email(self): return self.__email
    @property
    def department(self): return self._department

    @abstractmethod
    def borrowing_limit(self):
        pass

    @abstractmethod
    def role_name(self):
        pass

    def can_request_borrowing(self):
        return self.role_name() in ("student", "faculty")
