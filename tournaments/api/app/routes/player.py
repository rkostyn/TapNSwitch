from fastapi import APIRouter, Depends, HTTPException
from app.db.mongo import MongoClient
from app.dependencies import get_mongo_client, get_current_user, rate_limit
from app.repositories.player_repository import PlayerRepository
from app.models.player import Player, PlayerCreate
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/player", tags=["Players"])


@router.post("", response_model=Player)
async def create_player(
    body: PlayerCreate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Creating player: %s", body.player_name)
    repo = PlayerRepository(mongo_client)
    try:
        return await repo.create_player(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[Player], dependencies=[Depends(rate_limit(60))])
async def get_players(
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = PlayerRepository(mongo_client)
    return await repo.get_players()


@router.get("/{player_id}", response_model=Player, dependencies=[Depends(rate_limit(60))])
async def get_player(
    player_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Fetching player %s", player_id)
    repo = PlayerRepository(mongo_client)
    result = await repo.get_player(player_id)
    if not result:
        raise HTTPException(status_code=404, detail="Player not found")
    return result


@router.delete("/{player_id}", status_code=204)
async def delete_player(
    player_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Deleting player %s", player_id)
    repo = PlayerRepository(mongo_client)
    if not await repo.delete_player(player_id):
        raise HTTPException(status_code=404, detail="Player not found")
