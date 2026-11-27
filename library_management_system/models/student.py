from .user import LibraryUser
class Student(LibraryUser):
    def borrowing_limit(self):
        return 3
    def role_name(self):
        return "student"
