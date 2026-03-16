===============
plone.typesense
===============

Typesense search engine integration for Plone

Features
--------

- Indexing of all or partial content of the Plone site in Typesense.
- In the typesense control panel, we can define the Typesense schema for all indexes inside our Typesense collection.
- If an index is removed from portal_catalog, we use that index from typesense.
- You can also list an index as Typesense only index, but then Plone will still have the standard index in portal_catalog, but it should not b e used by queries.
- You can still keep some indexes inside Plone's portal_catalog and they will be used directly from there by internal queries. Typesense will index the data for those indexes too and you can also query it directly via Typesense API.

Goals
-----

plone.typesense is meant to be a full Plone integration, including permissions/roles.
You will be able to query Typesense directly from a client and also get all data from there.
This much faster than querying Plone which queries Typesense and you have the full query power of Typesense.
But everything inside Plone will work as expected, this includes searching and listing content via Plone's internal Python API's. So plone.api and restapi should have all known API calls.
They are limited to what Plone offers with the default search though.


Installation
------------

```sh
uv add plone.typesense
```

Start Plone and configure the typesense connection in the control panel.


Typesense
.........

This package requires a typesense search engine running.

You can run one by using `podman-compose` up or `docker compose up`.

Please read this for a [quick docker based setup](https://typesense.org/docs/guide/install-typesense.html#option-2-local-machine-self-hosting).

A nice UI is also available here: https://github.com/bfritscher/typesense-dashboard/releases


Usage
-----

http://localhost/Plone/@@typesense_controlpanel-controlpanel
http://localhost/Plone/@@typesense-reindex-collection
http://localhost/Plone/@@typesense-sync
http://localhost/Plone/@@typesense-convert
http://localhost/Plone/@@typesense-scoped-search-key




Authors
-------

Maik Derstappen - MrTango - md@derico.de


Contributors
------------

Put your name here, you deserve it!

- ?


Contribute
----------

- Issue Tracker: https://github.com/collective/plone.typesense/issues
- Source Code: https://github.com/collective/plone.typesense


Support
-------

If you are having issues, please let us know.


License
-------

The project is licensed under the GPLv2.
