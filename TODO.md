# TODO

- implement renaming and updating of TS collections, use export/import and aliases for this
- to improve updating further, we might need to send new index data to new and old collection for a moment, until we switch the alias
- allow choosing which indexes are indexed in Typesense and which are indexed in Plone's internal catalog
- use scoped token's to filter what the user can find
- filter out all fields with field level read permissions set, they can be fetch separately or added later with a separate Typesense collection
