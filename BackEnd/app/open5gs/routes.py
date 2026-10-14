from fastapi import APIRouter

from app.open5gs.client import Open5GSClient


router = APIRouter(
    prefix="/open5gs",
    tags=["Open5GS"]
)

open5gs = Open5GSClient("192.168.0.175")


@router.get("/ues")
async def get_ues():

    return await open5gs.get_amf_ues()


@router.get("/gnbs")
async def get_gnbs():

    return await open5gs.get_gnbs()


@router.get("/sessions")
async def get_sessions():

    return await open5gs.get_smf_sessions()