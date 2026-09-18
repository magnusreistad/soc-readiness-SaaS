import httpx
import os

from fastapi import HTTPException, status

GITHUB_API = "https://api.github.com"


def _get_headers() -> dict:
    pat = os.environ.get("GITHUB_PAT")
    if not pat:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub integration not configured.",
        )
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
    }

async def get_branch_protection(owner: str, repo: str, branch: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/branches/{branch}/protection",
            headers=_get_headers(),
        )
        if resp.status_code == 404:
            return None  # no protection configured — a real finding, not an error
        resp.raise_for_status()
        return resp.json()

async def list_pull_requests(owner: str, repo: str, state: str = "all"):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            headers=_get_headers(),
            params={"state": state},
        )
        resp.raise_for_status()
        return resp.json()

async def list_commits(owner: str, repo: str, since: str = None, until: str = None):
    params = {k: v for k, v in {"since": since, "until": until}.items() if v}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits",
            headers=_get_headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()