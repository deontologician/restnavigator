Changelog
=========

Unreleased
----------

- TBD

1.0
---

- Embedded support
- Ability to specify default curies
- Resources with no URL are now represented by a special Navigator type called OrphanNavigators
- IP addresses can be used in the url (@dudycooly)
- All tests pass in python 2.6 -> 3.4 (@bubenkoff), and travis now runs tox to ensure they stay that way
- Support the DELETE, and PATCH methods
- posts allow an empty body (@bbsgfalconer)
- Much improved content negotiation (@bbsgfalconer)
- There was also a major refactoring that changed how Navigators are created and internally cleaned up a
    lot of really messy code.
