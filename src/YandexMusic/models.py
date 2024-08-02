from pydantic import BaseModel, Field


class Artist(BaseModel):
    id: int
    name: str


class Album(BaseModel):
    id: int
    title: str


class Track(BaseModel):
    id: int
    real_id: int = Field(alias="realId")
    title: str
    available: bool
    duration_ms: int = Field(alias="durationMs")
    artists: list[Artist]
    thumbnail: str | None = Field(alias="coverUri", default=None)
    albums: list[Album]


class TrackList(BaseModel):
    tracks: list[Track] = []
    count: int = 0
    total: int = 0
