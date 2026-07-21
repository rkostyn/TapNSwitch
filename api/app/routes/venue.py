from fastapi import APIRouter, Depends

from app.db.mongo import MongoClient
from app.dependencies import get_current_user, get_mongo_client
from app.models.venue import VenueArenasResponse, VenueArenasUpdate
from app.repositories.venue_repository import VenueRepository

router = APIRouter(prefix="/venue", tags=["Venue"])


@router.get("/arenas", response_model=VenueArenasResponse)
async def get_venue_arenas(
    _: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = VenueRepository(mongo_client)
    return VenueArenasResponse(arenas=await repo.get_arenas())


@router.put("/arenas", response_model=VenueArenasResponse)
async def update_venue_arenas(
    body: VenueArenasUpdate,
    _: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = VenueRepository(mongo_client)
    arenas = await repo.set_arenas(body.arenas)
    return VenueArenasResponse(arenas=arenas)
