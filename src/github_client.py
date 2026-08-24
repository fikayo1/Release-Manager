"""Small direct GitHub REST adapter; :meth:`create_release` is its only write method."""
from typing import Any, Callable
import json
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .models import Evidence, Release, Repository


class _Response:
    def __init__(self, status_code, headers, payload):
        self.status_code, self.headers, self._payload = status_code, headers, payload

    def json(self):
        return json.loads(self._payload.decode("utf-8"))


def _stdlib_request(method, url, headers=None, timeout=20, params=None, json=None):
    """Minimal requests-compatible transport, also used by real acceptance tests."""
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    data = None if json is None else __import__("json").dumps(json).encode("utf-8")
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        response = urlopen(request, timeout=timeout)
        return _Response(response.status, dict(response.headers), response.read())
    except HTTPError as exc:
        return _Response(exc.code, dict(exc.headers), exc.read())


class GitHubError(RuntimeError):
    """A safe, operator-readable GitHub API failure."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GitHubTransportError(GitHubError):
    pass


class GitHubClient:
    def __init__(self, owner: str, repo: str, token: str, request: Callable[..., Any] = _stdlib_request):
        self.owner, self.repo, self._token, self._request = owner, repo, token, request
        self.base = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"

    def __repr__(self) -> str:
        return f"GitHubClient(repository={self.owner}/{self.repo}, token='***')"

    def _safe(self, value: Any) -> str:
        # GitHub messages should never echo credentials, but redaction here makes
        # that an invariant even for an injected enterprise transport.
        message = str(value or "").replace(self._token, "***")
        return message[:1000]

    def _call(self, method: str, url: str, **kwargs: Any) -> tuple[Any, Any]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "release-manager/1",
        }
        try:
            response = self._request(method, url, headers=headers, timeout=20, **kwargs)
        except Exception as exc:
            raise GitHubTransportError(
                f"GitHub transport failed for repository {self.owner}/{self.repo}"
            ) from exc
        if response.status_code >= 400:
            try:
                payload = response.json()
                message = payload.get("message", "") if isinstance(payload, dict) else ""
            except Exception:
                message = ""
            if response.status_code == 401:
                message = "authentication failed"
            elif response.status_code == 404:
                message = f"repository {self.owner}/{self.repo} not found or not readable"
            elif response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
                message = (
                    "GitHub rate limit exceeded; resets at "
                    + response.headers.get("X-RateLimit-Reset", "unknown")
                )
            raise GitHubError(
                self._safe(message) or f"GitHub returned HTTP {response.status_code}",
                response.status_code,
            )
        try:
            return response, response.json()
        except Exception as exc:
            raise GitHubError("GitHub returned malformed JSON", response.status_code) from exc

    @staticmethod
    def _malformed(exc: Exception) -> GitHubError:
        return GitHubError("GitHub returned a malformed response")

    def repository(self) -> Repository:
        _, data = self._call("GET", self.base)
        try:
            return Repository(data["default_branch"], data["created_at"], data["html_url"])
        except (KeyError, TypeError) as exc:
            raise self._malformed(exc) from exc

    def latest_release(self) -> Release | None:
        try:
            _, data = self._call("GET", self.base + "/releases/latest")
        except GitHubError as exc:
            if exc.status_code == 404:
                return None
            raise
        return self._release(data)

    def _pages(self, url: str, params: dict[str, Any]):
        while url:
            response, data = self._call("GET", url, params=params)
            if not isinstance(data, list):
                raise GitHubError("GitHub returned a malformed paginated response")
            yield data
            params, url = {}, ""
            for part in response.headers.get("Link", "").split(","):
                if 'rel="next"' in part:
                    url = part.split(";")[0].strip()[1:-1]

    def commits_since(self, cutoff: str, branch: str) -> tuple[Evidence, ...]:
        out = []
        try:
            for page in self._pages(
                self.base + "/commits", {"since": cutoff, "sha": branch, "per_page": 100}
            ):
                for data in page:
                    commit = data["commit"]
                    date = commit["committer"]["date"]
                    if date > cutoff:
                        out.append(
                            Evidence(
                                data["sha"],
                                "commit",
                                commit["message"].splitlines()[0],
                                (data.get("author") or {}).get("login")
                                or commit["author"]["name"],
                                date,
                                data["html_url"],
                                sha=data["sha"],
                            )
                        )
        except (KeyError, TypeError, AttributeError) as exc:
            raise self._malformed(exc) from exc
        return tuple(out)

    def merged_pulls_since(self, cutoff: str) -> tuple[Evidence, ...]:
        out = []
        try:
            for page in self._pages(
                self.base + "/pulls",
                {"state": "closed", "sort": "updated", "direction": "desc", "per_page": 100},
            ):
                for data in page:
                    if data.get("merged_at") and data["merged_at"] > cutoff:
                        out.append(
                            Evidence(
                                f"PR-{data['number']}",
                                "pull",
                                data["title"],
                                data["user"]["login"],
                                data["merged_at"],
                                data["html_url"],
                                tuple(label["name"] for label in data.get("labels", [])),
                                data.get("merge_commit_sha") or "",
                            )
                        )
                if page and all(data["updated_at"] <= cutoff for data in page):
                    break
        except (KeyError, TypeError, AttributeError) as exc:
            raise self._malformed(exc) from exc
        return tuple(out)

    def release_for_tag(self, tag: str) -> Release | None:
        try:
            _, data = self._call("GET", self.base + f"/releases/tags/{quote(tag, safe='')}")
        except GitHubError as exc:
            if exc.status_code == 404:
                return None
            raise
        return self._release(data)

    def create_release(self, tag: str, title: str, body: str) -> Release:
        _, data = self._call(
            "POST",
            self.base + "/releases",
            json={
                "tag_name": tag,
                "name": title,
                "body": body,
                "draft": False,
                "prerelease": False,
            },
        )
        return self._release(data)

    @staticmethod
    def _release(data: dict[str, Any]) -> Release:
        try:
            return Release(
                data["tag_name"],
                data.get("name") or "",
                data.get("body") or "",
                data.get("published_at") or data["created_at"],
                data["html_url"],
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise GitHubError("GitHub returned a malformed release response") from exc
