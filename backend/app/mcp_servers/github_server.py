"""GitHub MCP server — per-request token, structured errors, no secrets in process."""
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("github", json_response=True)

BASE = "https://api.github.com"
TIMEOUT = 20.0


def _client(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BASE,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=TIMEOUT,
        follow_redirects=True,
    )


@mcp.tool()
async def get_diff(owner: str, repo: str, pr_number: int, token: str) -> dict:
    """Return the unified diff for a pull request. token is the caller's GitHub PAT."""
    try:
        async with _client(token) as c:
            r = await c.get(
                f"/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={"Accept": "application/vnd.github.v3.diff"},
            )
            if r.status_code == 404:
                return {"ok": False, "error": "not_found",
                        "detail": f"{owner}/{repo}#{pr_number} not found or token lacks access"}
            if r.status_code == 403:
                return {"ok": False, "error": "forbidden",
                        "detail": "token lacks pull_request read scope"}
            r.raise_for_status()
            return {"ok": True, "diff": r.text}
    except httpx.TimeoutException:
        return {"ok": False, "error": "timeout", "detail": "github timeout"}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "error": "http_error",
                "detail": f"{e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "unexpected", "detail": repr(e)}


@mcp.tool()
async def post_review_comment(
    owner: str, repo: str, pr_number: int, path: str, line: int, body: str, token: str
) -> dict:
    """Post one inline review comment on a PR at (path, line on the new side)."""
    if not body.strip():
        return {"ok": False, "error": "invalid_input", "detail": "empty body"}
    try:
        async with _client(token) as c:
            r = await c.post(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
                json={"body": body, "path": path, "line": line, "side": "RIGHT"},
            )
            if r.status_code == 422:
                return {"ok": False, "error": "unprocessable",
                        "detail": "line not in diff or path unknown"}
            if r.status_code == 403:
                return {"ok": False, "error": "forbidden",
                        "detail": "token lacks pull_request write scope"}
            r.raise_for_status()
            data = r.json()
            return {"ok": True, "comment_id": data["id"], "html_url": data["html_url"]}
    except httpx.TimeoutException:
        return {"ok": False, "error": "timeout", "detail": "github timeout"}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "error": "http_error",
                "detail": f"{e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "unexpected", "detail": repr(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")