"""Synonym support for Typesense collections.

Parses synonym configuration text and syncs synonyms to Typesense.

Format:
  - Multi-way: word1, word2, word3
  - One-way: root => synonym1, synonym2
"""

from plone.typesense import log


def parse_synonyms(text):
    """Parse synonym configuration text into a list of synonym dicts.

    Each line defines one synonym rule.
    Multi-way format: word1, word2, word3
    One-way format:   root => synonym1, synonym2

    Returns a list of dicts ready for Typesense's synonyms API.
    """
    if not text:
        return []

    synonyms = []
    for i, line in enumerate(text.strip().splitlines()):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        synonym_id = f"synonym-rule-{i}"

        if "=>" in line:
            # One-way synonym
            parts = line.split("=>", 1)
            root = parts[0].strip()
            syns = [s.strip() for s in parts[1].split(",") if s.strip()]
            if root and syns:
                synonyms.append(
                    {
                        "id": synonym_id,
                        "root": root,
                        "synonyms": syns,
                    }
                )
        else:
            # Multi-way synonym
            words = [w.strip() for w in line.split(",") if w.strip()]
            if len(words) >= 2:
                synonyms.append(
                    {
                        "id": synonym_id,
                        "synonyms": words,
                    }
                )

    return synonyms


def sync_synonyms(client, collection_name, synonym_rules):
    """Sync synonym rules to a Typesense collection.

    First retrieves existing synonyms and removes them,
    then upserts the new synonym rules.

    :param client: Typesense client instance
    :param collection_name: Name of the collection
    :param synonym_rules: List of synonym dicts from parse_synonyms()
    :returns: tuple of (upserted_count, errors)
    """
    errors = []

    # Remove existing synonyms
    try:
        existing = client.collections[collection_name].synonyms.retrieve()
        for syn in existing.get("synonyms", []):
            try:
                client.collections[collection_name].synonyms[syn["id"]].delete()
            except Exception as e:
                log.warning(f"Failed to delete synonym {syn['id']}: {e}")
    except Exception as e:
        log.warning(f"Failed to retrieve existing synonyms: {e}")

    # Upsert new synonyms
    upserted = 0
    for rule in synonym_rules:
        synonym_id = rule.pop("id")
        try:
            client.collections[collection_name].synonyms.upsert(
                synonym_id, rule
            )
            upserted += 1
        except Exception as e:
            errors.append(f"Failed to upsert synonym '{synonym_id}': {e}")
            log.error(f"Failed to upsert synonym '{synonym_id}': {e}")

    return upserted, errors
