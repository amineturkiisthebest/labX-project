# open5gs/client.py

import httpx


class Open5GSClient:

    def __init__(self, host, info_port=9090):
        self.host = host
        self.info_port = info_port

    async def get_amf_ues(self):
        url = f"http://{self.host}:{self.info_port}/ue-info"
        print(f"[Open5GS] Requesting: {url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        response.raise_for_status()

        return response.json()

    async def get_gnbs(self):
        url = f"http://{self.host}:9090/gnb-info"

        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        response.raise_for_status()

        return response.json()

    async def get_smf_sessions(self):
        url = f"http://{self.host}:9090/pdu-info"

        async with httpx.AsyncClient() as client:
            response = await client.get(url)

        response.raise_for_status()

        return response.json()