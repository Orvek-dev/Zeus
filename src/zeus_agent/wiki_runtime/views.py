from __future__ import annotations

from zeus_agent.memory_graph_runtime import MemoryGraphStore

from .models import WikiPage


def render_wiki_page(store: MemoryGraphStore, subject: str) -> WikiPage:
    facts = store.facts_for_subject(subject)
    lines = [subject.strip()]
    for fact in facts:
        lines.append("{0}: {1}".format(fact.predicate, fact.object_text))
    return WikiPage(subject=subject.strip(), body="\n".join(lines), fact_count=len(facts))
