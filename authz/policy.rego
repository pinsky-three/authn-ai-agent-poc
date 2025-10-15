package policy

# This catches all paths under policy.* and evaluates authorization
default result = {"allowed": false}

# Catch-all rule for any path query
result = {"allowed": true} if {
  input.attributes.request.http.method == "GET"
  startswith(input.attributes.request.http.path, "/acme/")
  authz := input.attributes.request.http.headers.authorization
  has_bearer(authz)
}

has_bearer(authz) if {
  # PoC: Accept any bearer token (JWT validation happens in Envoy)
  # In production, parse claims forwarded from Envoy and enforce scope/role checks
  is_string(authz)
  authz != ""
  contains(lower(authz), "bearer ")
}
