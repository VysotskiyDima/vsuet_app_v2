from pydantic import BaseModel




class StudentExistsModel(BaseModel):
    zach_number: str
    exists: bool