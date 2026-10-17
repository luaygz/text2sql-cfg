"""Versioned prompt templates stored as YAML under `prompts/`.

Each file holds a `version`, a `changelog` and named `sections`. Sections use `string.Template`
placeholders (`$question`, `${schema}`), so literal braces in SQL or JSON examples need no
escaping. Rendering fails loudly on a missing placeholder. Any change to a prompt's text must bump
its version and add a changelog entry; the response cache keys on the rendered text, so stale
cached answers can never be served for an edited prompt.
"""

from __future__ import annotations

import string
from datetime import date
from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from text2sql.config import REPO_ROOT

PROMPTS_DIR = REPO_ROOT / "prompts"


class ChangelogEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    date: date
    note: str


class PromptTemplate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    version: str
    description: str
    changelog: list[ChangelogEntry] = Field(min_length=1)
    sections: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def _version_is_logged(self) -> PromptTemplate:
        if self.changelog[-1].version != self.version:
            raise ValueError(
                f"prompt {self.name!r}: version {self.version} has no changelog entry "
                f"(last entry is {self.changelog[-1].version})"
            )
        return self

    @property
    def tag(self) -> str:
        """`name@version`, recorded with every call that used this template."""
        return f"{self.name}@{self.version}"

    def render(self, section: str, **values: str) -> str:
        try:
            text = self.sections[section]
        except KeyError:
            raise KeyError(f"prompt {self.name!r} has no section {section!r}") from None
        return string.Template(text).substitute(values).strip()


def load_prompt(name: str, directory: Path = PROMPTS_DIR) -> PromptTemplate:
    return _load(name, directory)


@cache
def _load(name: str, directory: Path) -> PromptTemplate:
    path = directory / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a mapping")
    if data.get("name") != name:
        raise ValueError(f"{path}: `name` must be {name!r}")
    return PromptTemplate.model_validate(data)
