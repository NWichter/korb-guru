"""Route schemas."""

from pydantic import BaseModel, Field


class RouteOptimizeRequest(BaseModel):
    selected_shops: list[str]
    time_limit: int = 45
    start_lat: float | None = Field(default=None, ge=-90, le=90)
    start_lng: float | None = Field(default=None, ge=-180, le=180)
    transport_mode: str = Field(
        default="walking",
        pattern="^(walking|cycling|driving)$",
        description="Transport mode: walking, cycling, or driving",
    )


class ProductInfo(BaseModel):
    name: str
    price: float | None = None
    category: str | None = None


class RouteStop(BaseModel):
    name: str
    task: str
    distance: str
    latitude: float | None = None
    longitude: float | None = None
    products: list[ProductInfo] = []


class RouteLeg(BaseModel):
    from_store: str | None = None
    to_store: str | None = None
    distance_m: float
    duration_min: float
    transport_mode: str


class RouteResponse(BaseModel):
    saved: float
    time: int
    stops: list[RouteStop]
    legs: list[RouteLeg] = []
    total_distance_m: float = 0.0
    total_duration_min: float = 0.0
