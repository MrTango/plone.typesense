Index Strategies
================

We have two indexing strategies.

## Plone's internal portal_catalog indexes

This is what come by default with Plone.
It can be beneficial to keep some of the simple indexes inside Plone, as queries might be quicker for operations like listing content.

## Typesense indexes

In general all more complex indexes should be handled in Typesense, as it is much faster and provides way more features for searching and finding content.

## Controlling where content is indexed and searched

- if we have an index in portal_catalog and it is not in the list of typesense only indexes, we index and search inside Plone. But the content is still also indexed in Typesense and could be also used there by direct Typesense API calls.
- if we have an index in portal_catalog but it is in the typesense only list. We index it on both sides, but querying it only from Typesense. It is recommended that one is removing the index from portal_catalog to save indexing time and speed up Plone's internal indexing.
- if we don't have a certain index inside portal_catalog we redirect the query to Typesense. For document reasons it's still recommended to add them to the typesense only list.

The most important indexes to have inside Typesense are SearchableText, Description and Title, but also things like Subjects, as they can be used for facetting content.

## Querying typesense directly

### Example query

```json
{
    'q': 'tango*',
    'query_by': 'SearchableText',
    'filter_by': "portal_type:=[`File`, `Collection`, `Document`, `Folder`, `Image`, `Event`, `Link`, `News Item`]",
    'per_page': 50,
    'page': 1
}
```
