from integrations.base import RawPosting, SearchQuery, SourceError


class FakeSource:
    def __init__(self, platform, postings=(), error=None, delay=0.0):
        self.platform, self.postings, self.error, self.delay = platform, list(postings), error, delay
        self.calls: list[SearchQuery] = []

    def search(self, query):
        import time
        self.calls.append(query)
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return list(self.postings)


def posting(platform, ext, title="ML Engineer", company="Razorpay", location="Bengaluru", **kw):
    return RawPosting(platform=platform, external_id=ext, url=f"https://example.com/{platform}/{ext}",
                      title=title, company=company, location=location,
                      description=kw.pop("description", "Python PyTorch SQL 1-3 years"), **kw)


def factory(sources):
    def build(platform):
        if platform not in sources:
            raise SourceError(f"no fake for {platform}")
        return sources[platform]
    return build
