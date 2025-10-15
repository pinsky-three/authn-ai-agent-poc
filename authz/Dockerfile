FROM openpolicyagent/opa:latest
COPY policy.rego /policy/policy.rego
CMD ["run", "--server", "--addr", "0.0.0.0:8181", "/policy"]
