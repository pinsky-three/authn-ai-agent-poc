package policy

default allow = false

# Allow GET requests to /acme/ with bearer token
allow {
  input.attributes.request.http.method == "GET"
  startswith(input.attributes.request.http.path, "/acme/")
  authz := input.attributes.request.http.headers.authorization
  has_bearer(authz)
}

has_bearer(authz) {
  # PoC: Accept any bearer token (JWT validation happens in Envoy)
  # In production, parse claims forwarded from Envoy and enforce scope/role checks
  lower(authz) != ""
  contains(lower(authz), "bearer ")
}
