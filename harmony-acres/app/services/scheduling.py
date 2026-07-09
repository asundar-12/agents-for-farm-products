from datetime import date

from fastapi import HTTPException, status

_WEDNESDAY = 2  # date.weekday(): Monday=0 ... Sunday=6


def assert_wednesday(value: date, field_name: str) -> None:
    if value.weekday() != _WEDNESDAY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must fall on a Wednesday",
        )
