import aiohttp

class Shortner:
    def __init__(self, api_key: str, base_site: str):
        self.api_key = api_key
        self.base_site = base_site
        self.base_url = f"https://{self.base_site}/api"

        if not self.api_key:
            raise Exception("Shortner API key not provided")

    async def __fetch(self, session: aiohttp.ClientSession, params: dict) -> dict:
        async with session.get(
            self.base_url, params=params, raise_for_status=True
        ) as response:
            result = await response.json(content_type="application/json")
            return result

    async def convert(
        self,
        link: str,
        alias: str = "",
    ) -> str:

        params = {
            "api": self.api_key,
            "url": link,
            "alias": alias,
            "format": "json",
        }

        try:
            my_conn = aiohttp.TCPConnector(limit=10)
            async with aiohttp.ClientSession(connector=my_conn) as session:
                session = session
                data = await self.__fetch(session, params)

                if data["status"] == "success":
                    return data["shortenedUrl"]

                raise Exception(data["message"])

        except Exception as e:
            raise Exception(e)

