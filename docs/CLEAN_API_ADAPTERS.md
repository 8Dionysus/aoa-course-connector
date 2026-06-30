# Clean API Adapter Notes

At least one clean API/LMS adapter should remain in the tree as a reference
shape. Stepik is now the first working target because its course export model
maps naturally to:

`course -> sections -> units -> lessons -> steps`

Moodle and Canvas are strong follow-up adapters because their course module APIs
can return course contents and files through official LMS routes.

See `docs/STEPIK.md` for the fixture route, bounded live API smoke, and
operator-selected full-course route with Stepik `ids[]` batching and optional
authenticated step-source enrichment.
