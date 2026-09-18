import httpx
import os

GITHUB_API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {os.environ['GITHUB_PAT']}",
    "Accept": "application/vnd.github+json",
}

async def get_branch_protection(owner: str, repo: str, branch: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/branches/{branch}/protection",
            headers=HEADERS,
        )
        if resp.status_code == 404:
            return None  # no protection configured — a real finding, not an error
        resp.raise_for_status()
        return resp.json()

async def list_pull_requests(owner: str, repo: str, state: str = "all"):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            headers=HEADERS,
            params={"state": state},
        )
        resp.raise_for_status()
        return resp.json()

async def list_commits(owner: str, repo: str, since: str = None, until: str = None):
    params = {k: v for k, v in {"since": since, "until": until}.items() if v}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits",
            headers=HEADERS,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()