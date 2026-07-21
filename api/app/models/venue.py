from pydantic import BaseModel, Field


class Arena(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    label: str = Field(min_length=1, max_length=128)


class VenueArenasResponse(BaseModel):
    arenas: list[Arena]


class VenueArenasUpdate(BaseModel):
    arenas: list[Arena] = Field(min_length=1, max_length=20)
