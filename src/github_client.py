"""Small direct GitHub REST adapter; create_release is its only write method."""
from typing import Any, Callable
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .models import Evidence, Release, Repository


class _Response:
    def __init__(self, status_code, headers, payload):
        self.status_code, self.headers, self._payload = status_code, headers, payload
    def json(self):
        return json.loads(self._payload.decode("utf-8"))


def _stdlib_request(method, url, headers=None, timeout=20, params=None, json=None):
    """Minimal requests-compatible transport, avoiding an undeclared runtime dependency."""
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params)
    data = None if json is None else __import__("json").dumps(json).encode("utf-8")
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        response = urlopen(request, timeout=timeout)
        return _Response(response.status, dict(response.headers), response.read())
    except HTTPError as exc:
        return _Response(exc.code, dict(exc.headers), exc.read())

class GitHubError(RuntimeError): pass
class GitHubTransportError(GitHubError): pass

class GitHubClient:
    def __init__(self, owner: str, repo: str, token: str, request: Callable[...,Any]=_stdlib_request):
        self.owner,self.repo,self._token,self._request=owner,repo,token,request
        self.base=f"https://api.github.com/repos/{owner}/{repo}"
    def _call(self, method: str, url: str, **kwargs: Any) -> Any:
        headers={"Authorization":f"Bearer {self._token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
        try: response=self._request(method,url,headers=headers,timeout=20,**kwargs)
        except Exception as exc: raise GitHubTransportError("GitHub transport failed") from exc
        if response.status_code >= 400:
            try: message=response.json().get("message","")
            except Exception: message=""
            if response.status_code==401: message="authentication failed"
            elif response.status_code==404: message=f"repository {self.owner}/{self.repo} not found or not readable"
            elif response.status_code==403 and response.headers.get("X-RateLimit-Remaining")=="0": message=f"GitHub rate limit exceeded; resets at {response.headers.get('X-RateLimit-Reset','unknown')}"
            raise GitHubError(message or f"GitHub returned HTTP {response.status_code}")
        try: return response, response.json()
        except Exception as exc: raise GitHubError("GitHub returned malformed JSON") from exc
    def repository(self) -> Repository:
        _,d=self._call("GET",self.base); return Repository(d["default_branch"],d["created_at"],d["html_url"])
    def latest_release(self) -> Release|None:
        try: _,d=self._call("GET",self.base+"/releases/latest")
        except GitHubError as exc:
            if "not found or not readable" in str(exc): return None
            raise
        return self._release(d)
    def _pages(self,url: str,params: dict[str,Any]):
        while url:
            response,data=self._call("GET",url,params=params); yield data
            params={}; url=""
            for part in response.headers.get("Link","").split(","):
                if 'rel="next"' in part: url=part.split(";")[0].strip()[1:-1]
    def commits_since(self, cutoff: str, branch: str) -> tuple[Evidence,...]:
        out=[]
        for page in self._pages(self.base+"/commits",{"since":cutoff,"sha":branch,"per_page":100}):
            for d in page:
                c=d["commit"]; date=c["committer"]["date"]
                if date>cutoff: out.append(Evidence(d["sha"],"commit",c["message"].splitlines()[0],(d.get("author") or {}).get("login") or c["author"]["name"],date,d["html_url"],sha=d["sha"]))
        return tuple(out)
    def merged_pulls_since(self, cutoff: str) -> tuple[Evidence,...]:
        out=[]
        for page in self._pages(self.base+"/pulls",{"state":"closed","sort":"updated","direction":"desc","per_page":100}):
            for d in page:
                if d.get("merged_at") and d["merged_at"]>cutoff: out.append(Evidence(f"PR-{d['number']}","pull",d["title"],d["user"]["login"],d["merged_at"],d["html_url"],tuple(x["name"] for x in d.get("labels",[])),d.get("merge_commit_sha") or ""))
            if page and all(d["updated_at"]<=cutoff for d in page): break
        return tuple(out)
    def release_for_tag(self,tag: str) -> Release|None:
        try: _,d=self._call("GET",self.base+f"/releases/tags/{tag}")
        except GitHubError as exc:
            if "not found or not readable" in str(exc): return None
            raise
        return self._release(d)
    def create_release(self,tag: str,title: str,body:str) -> Release:
        _,d=self._call("POST",self.base+"/releases",json={"tag_name":tag,"name":title,"body":body,"draft":False,"prerelease":False})
        return self._release(d)
    @staticmethod
    def _release(d:dict[str,Any])->Release: return Release(d["tag_name"],d.get("name") or "",d.get("body") or "",d.get("published_at") or d.get("created_at"),d["html_url"])
