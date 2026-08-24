from src.github_client import GitHubClient
class Response:
 status_code=200
 headers={}
 def json(self): return {"default_branch":"main","created_at":"2020-01-01T00:00:00Z","html_url":"https://github/o/r"}
def test_headers_are_pinned_and_token_is_only_header():
 calls=[]
 def request(*args,**kwargs): calls.append((args,kwargs)); return Response()
 assert GitHubClient("o","r","secret",request).repository().default_branch=="main"
 headers=calls[0][1]["headers"]
 assert headers["Authorization"]=="Bearer secret" and headers["X-GitHub-Api-Version"]=="2022-11-28"
