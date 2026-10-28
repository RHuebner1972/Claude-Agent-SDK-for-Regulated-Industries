# The compliance suites in solution/compliance and starter/compliance are run on purpose by the Lab 6 tests (and by
# `cd solution && pytest compliance`), never collected as part of the lab's own tests.
collect_ignore = ["solution", "starter"]
