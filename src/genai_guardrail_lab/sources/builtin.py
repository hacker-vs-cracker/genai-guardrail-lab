from __future__ import annotations

import csv
import json
import urllib.parse
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import requests

from genai_guardrail_lab.models import PromptCase
from genai_guardrail_lab.registry import SOURCE_REGISTRY
from genai_guardrail_lab.sources.base import BaseSource
from genai_guardrail_lab.utils import date_only, first_value

USER_AGENT = "GenAI-Guardrail-Lab/0.2 (+defensive-security-research)"
DEFAULT_PROMPT_FIELDS = ["prompt", "text", "instruction", "attack", "user_input", "content"]
DEFAULT_CATEGORY_FIELDS = ["category", "label", "type", "source"]


def _case_from_mapping(
    *,
    source_name: str,
    source_type: str,
    source_url: str,
    row: dict[str, Any],
    index: int,
    config: dict[str, Any],
) -> PromptCase | None:
    prompt = first_value(row, config.get("prompt_fields", DEFAULT_PROMPT_FIELDS))
    if not prompt:
        return None
    default_date = str(config.get("default_published_at", "2026-01-01"))
    return PromptCase(
        source_name=source_name,
        source_type=source_type,
        source_url=source_url,
        title=str(row.get("title") or f"{source_name}:{index}"),
        category=str(first_value(row, config.get("category_fields", DEFAULT_CATEGORY_FIELDS)) or source_type),
        content=str(prompt),
        published_at=date_only(first_value(row, ["published_at", "created_at", "date"]), default_date),
        executable=bool(config.get("execute", True)),
        metadata={"record_index": index, "fields": sorted(row)},
    )


@SOURCE_REGISTRY.register("jsonl_file")
class JsonlFileSource(BaseSource):
    def fetch(self) -> Iterable[PromptCase]:
        path = Path(self.config["path"])
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                case = _case_from_mapping(
                    source_name=self.name,
                    source_type="jsonl_file",
                    source_url=str(path),
                    row=row,
                    index=line_number,
                    config=self.config,
                )
                if case:
                    yield case


@SOURCE_REGISTRY.register("jsonl_url")
class JsonlUrlSource(BaseSource):
    def fetch(self) -> Iterable[PromptCase]:
        url = str(self.config["url"])
        response = requests.get(url, timeout=self._timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        for line_number, line in enumerate(response.text.splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            case = _case_from_mapping(
                source_name=self.name,
                source_type="jsonl_url",
                source_url=url,
                row=row,
                index=line_number,
                config=self.config,
            )
            if case:
                yield case

    @property
    def _timeout(self) -> int:
        return int(self.global_config["collection"]["request_timeout_seconds"])


@SOURCE_REGISTRY.register("csv_url")
class CsvUrlSource(BaseSource):
    def fetch(self) -> Iterable[PromptCase]:
        url = str(self.config["url"])
        response = requests.get(url, timeout=self._timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        for row_number, row in enumerate(csv.DictReader(response.text.splitlines()), 1):
            case = _case_from_mapping(
                source_name=self.name,
                source_type="csv_url",
                source_url=url,
                row=dict(row),
                index=row_number,
                config=self.config,
            )
            if case:
                yield case

    @property
    def _timeout(self) -> int:
        return int(self.global_config["collection"]["request_timeout_seconds"])


@SOURCE_REGISTRY.register("huggingface_rows")
class HuggingFaceRowsSource(BaseSource):
    """Read a bounded slice from the Hugging Face datasets-server API."""

    def fetch(self) -> Iterable[PromptCase]:
        dataset = str(self.config["dataset"])
        dataset_config = str(self.config.get("config", "default"))
        split = str(self.config.get("split", "train"))
        offset = int(self.config.get("offset", 0))
        length = min(int(self.config.get("length", 100)), 1000)
        params = {
            "dataset": dataset,
            "config": dataset_config,
            "split": split,
            "offset": offset,
            "length": length,
        }
        url = "https://datasets-server.huggingface.co/rows?" + urllib.parse.urlencode(params)
        response = requests.get(url, timeout=self._timeout, headers={"User-Agent": USER_AGENT})

        if response.status_code >= 400 and dataset_config in {"", "default", "auto"}:
            split_url = "https://datasets-server.huggingface.co/splits?" + urllib.parse.urlencode({"dataset": dataset})
            split_response = requests.get(split_url, timeout=self._timeout, headers={"User-Agent": USER_AGENT})
            split_response.raise_for_status()
            available = split_response.json().get("splits", [])
            if available:
                params["config"] = available[0]["config"]
                params["split"] = available[0]["split"]
                url = "https://datasets-server.huggingface.co/rows?" + urllib.parse.urlencode(params)
                response = requests.get(url, timeout=self._timeout, headers={"User-Agent": USER_AGENT})

        response.raise_for_status()
        for item in response.json().get("rows", []):
            row = item.get("row") or {}
            index = int(item.get("row_idx", 0))
            case = _case_from_mapping(
                source_name=self.name,
                source_type="huggingface_rows",
                source_url=f"https://huggingface.co/datasets/{dataset}",
                row=row,
                index=index,
                config=self.config,
            )
            if case:
                case.metadata.update({"dataset": dataset, "dataset_config": params["config"], "split": params["split"]})
                yield case

    @property
    def _timeout(self) -> int:
        return int(self.global_config["collection"]["request_timeout_seconds"])


@SOURCE_REGISTRY.register("arxiv_intel")
class ArxivIntelSource(BaseSource):
    """Collect paper metadata as non-executable research intelligence."""

    def fetch(self) -> Iterable[PromptCase]:
        query = str(self.config.get("query", 'all:"prompt injection" OR all:"jailbreak"'))
        max_results = min(int(self.config.get("max_results", 25)), 100)
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
        response = requests.get(url, timeout=self._timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()

        root = ET.fromstring(response.text)
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        for index, entry in enumerate(root.findall("atom:entry", namespace), 1):
            title = " ".join((entry.findtext("atom:title", default="", namespaces=namespace)).split())
            summary = " ".join((entry.findtext("atom:summary", default="", namespaces=namespace)).split())
            published = entry.findtext("atom:published", default="", namespaces=namespace)
            entry_url = entry.findtext("atom:id", default="", namespaces=namespace)
            if not summary:
                continue
            yield PromptCase(
                source_name=self.name,
                source_type="arxiv_intel",
                source_url=entry_url,
                title=title or f"arXiv result {index}",
                category="research_intelligence",
                content=summary,
                published_at=date_only(published, "2026-01-01"),
                executable=False,
                metadata={"query": query, "record_index": index},
            )

    @property
    def _timeout(self) -> int:
        return int(self.global_config["collection"]["request_timeout_seconds"])


@SOURCE_REGISTRY.register("github_releases_intel")
class GitHubReleasesIntelSource(BaseSource):
    """Track release notes without treating them as executable prompts."""

    def fetch(self) -> Iterable[PromptCase]:
        repository = str(self.config["repository"])
        limit = min(int(self.config.get("limit", 10)), 50)
        url = f"https://api.github.com/repos/{repository}/releases?per_page={limit}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
        token_env = str(self.config.get("token_env", "GITHUB_TOKEN"))
        import os

        if os.getenv(token_env):
            headers["Authorization"] = f"Bearer {os.environ[token_env]}"
        response = requests.get(url, timeout=self._timeout, headers=headers)
        response.raise_for_status()
        for index, release in enumerate(response.json(), 1):
            body = str(release.get("body") or release.get("name") or release.get("tag_name") or "")
            if not body.strip():
                continue
            yield PromptCase(
                source_name=self.name,
                source_type="github_releases_intel",
                source_url=str(release.get("html_url") or ""),
                title=str(release.get("name") or release.get("tag_name") or f"Release {index}"),
                category="tool_release_intelligence",
                content=body,
                published_at=date_only(release.get("published_at"), "2026-01-01"),
                executable=False,
                metadata={"repository": repository, "tag": release.get("tag_name", "")},
            )

    @property
    def _timeout(self) -> int:
        return int(self.global_config["collection"]["request_timeout_seconds"])


@SOURCE_REGISTRY.register("rss_intel")
class RssIntelSource(BaseSource):
    """Read RSS/Atom entries as intelligence only; no blog prompt scraping."""

    def fetch(self) -> Iterable[PromptCase]:
        url = str(self.config["url"])
        limit = min(int(self.config.get("limit", 25)), 100)
        response = requests.get(url, timeout=self._timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        root = ET.fromstring(response.content)

        entries = root.findall(".//item")
        atom_namespace = {"atom": "http://www.w3.org/2005/Atom"}
        if not entries:
            entries = root.findall("atom:entry", atom_namespace)

        for index, entry in enumerate(entries[:limit], 1):
            if entry.tag.endswith("entry"):
                title = entry.findtext("atom:title", default="", namespaces=atom_namespace)
                summary = entry.findtext("atom:summary", default="", namespaces=atom_namespace) or entry.findtext(
                    "atom:content", default="", namespaces=atom_namespace
                )
                published = entry.findtext("atom:published", default="", namespaces=atom_namespace) or entry.findtext(
                    "atom:updated", default="", namespaces=atom_namespace
                )
                link_node = entry.find("atom:link", atom_namespace)
                link = link_node.attrib.get("href", "") if link_node is not None else ""
            else:
                title = entry.findtext("title", default="")
                summary = entry.findtext("description", default="")
                published = entry.findtext("pubDate", default="")
                link = entry.findtext("link", default="")

            plain_summary = " ".join(str(summary).split())
            if not plain_summary:
                continue
            yield PromptCase(
                source_name=self.name,
                source_type="rss_intel",
                source_url=link,
                title=" ".join(str(title).split()) or f"Feed entry {index}",
                category="blog_intelligence",
                content=plain_summary,
                published_at=date_only(published, str(self.config.get("default_published_at", "2026-01-01"))),
                executable=False,
                metadata={"feed_url": url, "record_index": index},
            )

    @property
    def _timeout(self) -> int:
        return int(self.global_config["collection"]["request_timeout_seconds"])
