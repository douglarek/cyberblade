import aiohttp

from app.config.settings import settings


class HTTPService:
    _conn = aiohttp.TCPConnector()
    session = aiohttp.ClientSession(connector=_conn)

    async def jinrishici_sentence(self):
        headers = {"X-User-Token": settings.jinrishici_token}
        async with self.session.get(settings.jinrishici_api_endpoint + "/sentence", headers=headers) as resp:
            if resp.status == 200:
                # {
                #     "status": "success",
                #     "data": {
                #         "id": "5b8b9572e116fb3714e6faba",
                #         "content": "君问归期未有期，巴山夜雨涨秋池。",
                #         "popularity": 1170000,
                #         "origin": {
                #             "title": "夜雨寄北",
                #             "dynasty": "唐代",
                #             "author": "李商隐",
                #             "content": [
                #                 "君问归期未有期，巴山夜雨涨秋池。",
                #                 "何当共剪西窗烛，却话巴山夜雨时。"
                #             ],
                #             "translate": [
                #                 "您问归期，归期实难说准，巴山连夜暴雨，涨满秋池。",
                #                 "何时归去，共剪西窗烛花，当面诉说，巴山夜雨况味。"
                #             ]
                #         },
                #         "matchTags": [
                #             "秋",
                #             "晚上"
                #         ],
                #         "recommendedReason": "",
                #         "cacheAt": "2018-09-17T21:18:44.693645"
                #     },
                #     "token": "6453911a-9ad7-457e-9b9d-c21011b85a0c",
                #     "ipAddress": "162.248.93.154"
                # }
                return await resp.json()
            return {
                "status": f"HTTP {resp.status} {resp.reason}",
            }
