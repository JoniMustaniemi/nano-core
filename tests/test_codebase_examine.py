from app.proactive.codebase_examine import CodebaseExamineService


class _CrawlClient:
    def complete(self, messages) -> str:
        return (
            '{"summary": "Main entrypoint.", '
            '"suggestion": "Add clearer health messages.", '
            '"confidence": "medium"}'
        )


def test_codebase_examine_alias_delegates_to_crawl(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.proactive.codebase_crawl.CodebaseCrawlService.scan_next_file",
        lambda self, client: "offer",
    )

    result = CodebaseExamineService().run(client=_CrawlClient())

    assert result == "offer"
