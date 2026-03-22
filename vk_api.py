import requests
import time
from config import VK_TOKEN, VK_API_VERSION, REQUEST_DELAY

class VKAPI:
    def __init__(self):
        self.token = VK_TOKEN
        self.version = VK_API_VERSION
        self.base_url = "https://api.vk.com/method/"
        self.last_request_time = 0

    def _request(self, method, params=None):
        if params is None:
            params = {}
        params["access_token"] = self.token
        params["v"] = self.version

        # Соблюдаем rate limits
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

        response = requests.get(self.base_url + method, params=params).json()
        self.last_request_time = time.time()

        if "error" in response:
            error_msg = response["error"].get("error_msg", "Unknown error")
            raise Exception(f"VK API error: {error_msg}")
        return response.get("response")

    def search_groups(self, query, count=1000):
        params = {
            "q": query,
            "type": "group",
            "count": min(count, 1000),
            "offset": 0
        }
        result = self._request("groups.search", params)
        return result.get("items", [])

    def get_group_info(self, group_ids):
        if isinstance(group_ids, list):
            group_ids = ",".join(str(g) for g in group_ids)
        params = {
            "group_ids": group_ids,
            "fields": "screen_name"
        }
        return self._request("groups.getById", params)

    def get_wall_posts(self, owner_id, count=100, offset=0):
        params = {
            "owner_id": owner_id,
            "count": count,
            "offset": offset
        }
        return self._request("wall.get", params)

    def get_comments(self, owner_id, post_id, count=100, offset=0):
        params = {
            "owner_id": owner_id,
            "post_id": post_id,
            "count": count,
            "offset": offset,
            "need_likes": 0,
            "preview_length": 0,
            "extended": 1
        }
        return self._request("wall.getComments", params)

    def get_users(self, user_ids):
        if not user_ids:
            return []
        params = {
            "user_ids": ",".join(str(uid) for uid in user_ids),
            "fields": "screen_name"
        }
        return self._request("users.get", params)