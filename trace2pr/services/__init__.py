"""Service layer: encapsulates Supabase queries and business rules, keeping
`api/routes/*.py` as thin HTTP controllers. Each service takes the
Supabase client and the current user dict handed to it by the route (via
the `supabase_dep` / `get_current_user` FastAPI dependencies) rather than
reaching for globals, so services stay easy to unit test."""
