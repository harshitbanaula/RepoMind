import httpx


class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_repo(self, full_name: str) -> dict:
        r = await self._client.get(f"/repos/{full_name}")
        r.raise_for_status()
        return r.json()