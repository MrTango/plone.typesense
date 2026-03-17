.. This README is meant for consumption by humans and PyPI. PyPI can render rst files so please do not use Sphinx features.
   If you want to learn more about writing documentation, please check out: http://docs.plone.org/about/documentation_styleguide.html
   This text does not appear on PyPI or github. It is a comment.

.. image:: https://github.com/collective/plone.typesense/actions/workflows/plone-package.yml/badge.svg
    :target: https://github.com/collective/plone.typesense/actions/workflows/plone-package.yml

.. image:: https://coveralls.io/repos/github/collective/plone.typesense/badge.svg?branch=main
    :target: https://coveralls.io/github/collective/plone.typesense?branch=main
    :alt: Coveralls

.. image:: https://codecov.io/gh/collective/plone.typesense/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/collective/plone.typesense

.. image:: https://img.shields.io/pypi/v/plone.typesense.svg
    :target: https://pypi.python.org/pypi/plone.typesense/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/status/plone.typesense.svg
    :target: https://pypi.python.org/pypi/plone.typesense
    :alt: Egg Status

.. image:: https://img.shields.io/pypi/pyversions/plone.typesense.svg?style=plastic   :alt: Supported - Python Versions

.. image:: https://img.shields.io/pypi/l/plone.typesense.svg
    :target: https://pypi.python.org/pypi/plone.typesense/
    :alt: License


===============
plone.typesense
===============

Typesense Plone integration (WIP!)

Features
--------

- Indexing of all or partial content of the Plone site in Typesense.


Goals
-----

plone.typesense is meant to be a full Plone integration, including permissions/roles.
You will be able to query Typesense directly from a client and also get all data from there.
This much faster than querying Plone which queries Typesense and you have the full query power of Typesense.
But everything inside Plone will work as expected. So plone.api/restapi should have all known API calls.
But they are limited to what Plone offers with the default search.


Installation
------------

Install plone.typesense by adding it to your buildout::

    [buildout]

    ...

    eggs =
        plone.typesense


and then running ``bin/buildout``

Typesense
.........

This package requires a typesense search engine running.

You can run one by using `podman-compose` up or `docker-compose up`.

Please read this for a [quick docker based setup](https://typesense.org/docs/guide/install-typesense.html#option-2-local-machine-self-hosting).

A nice UI is also available here: https://github.com/bfritscher/typesense-dashboard/releases

Usage
-----

http://localhost/Plone/@@typesense-test-connection
http://localhost/Plone/@@typesense-reindex-collection


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
- Source Code: https://github.com/collective/plone.typesens


Support
-------

If you are having issues, please let us know.


License
-------

The project is licensed under the GPLv2.
