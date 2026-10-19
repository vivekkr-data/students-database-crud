"""Request validation shared by create, replace and partial update."""
from datetime import date
from typing import Annotated
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Name = Annotated[str, Field(min_length=2, max_length=100)]
ShortText = Annotated[str, Field(min_length=1, max_length=100)]
Phone = Annotated[str, Field(min_length=7, max_length=25)]
Address = Annotated[str, Field(min_length=1, max_length=300)]


class StudentFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("date_of_birth", check_fields=False)
    @classmethod
    def valid_birth_date(cls, value):
        if value is not None and (value > date.today() or value.year < 1900):
            raise ValueError("Date of birth must be between 1900-01-01 and today")
        return value

    @field_validator("email", check_fields=False)
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower() if value is not None else None

    @field_validator("phone", check_fields=False)
    @classmethod
    def valid_phone(cls, value):
        if value is not None:
            digits = re.sub(r"\D", "", value)
            if not re.fullmatch(r"\+?[0-9 ()-]+", value) or not 7 <= len(digits) <= 15:
                raise ValueError("Phone must contain 7-15 digits; +, spaces, () and - are allowed")
        return value


class StudentCreate(StudentFields):
    name: Name
    date_of_birth: date
    email: EmailStr | None = None
    phone: Phone | None = None
    course: ShortText | None = None
    address: Address | None = None
    enrollment_date: date | None = None

    @model_validator(mode="after")
    def validate_record(self):
        if not (self.email or self.phone):
            raise ValueError("Provide at least an email or phone")
        if self.enrollment_date and self.enrollment_date < self.date_of_birth:
            raise ValueError("Enrollment date cannot precede date of birth")
        return self


class StudentPatch(StudentFields):
    name: Name | None = None
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: Phone | None = None
    course: ShortText | None = None
    address: Address | None = None
    enrollment_date: date | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("Supply at least one field")
        for field in ("name", "date_of_birth"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class StudentOut(StudentCreate):
    student_id: int


class StudentPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[StudentOut]


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=3, max_length=500)
