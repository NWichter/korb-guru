from pydantic import BaseModel


class StoreLocation(BaseModel):
    chain: str
    name: str
    address: str = ""
    plz: str = ""
    city: str = ""
    lat: float | None = None
    lon: float | None = None
    opening_hours: str | None = None
