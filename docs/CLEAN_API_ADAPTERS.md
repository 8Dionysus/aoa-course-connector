# Clean API Adapter Notes

At least one clean API/LMS adapter should remain in the tree as a reference
shape. Stepik is the first target because its course export model maps naturally
to:

`course -> sections -> units -> lessons -> steps`

Moodle and Canvas are strong follow-up adapters because their course module APIs
can return course contents and files through official LMS routes.
