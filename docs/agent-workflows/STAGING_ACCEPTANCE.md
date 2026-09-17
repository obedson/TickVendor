# Staging acceptance workflow

For manual or deployed acceptance against a real environment. This is external verification and must never be converted into local verification, or the reverse.

## 1. Establish the target

* Identify the exact deployed commit and the environment before testing.
* Distinguish deployed code from local code. Do not re-test local behaviour and record it as staging evidence.

## 2. Record evidence

* Account role and tenant context, never credentials or secrets.
* The exact action taken and the exact observed result, including HTTP status, relevant response body, and UI state.
* Provider-side evidence such as delivery records or provider references where the requirement depends on them.
* Do not infer a cause such as "internet problem", "cold start", "cache", or "deploy lag" without evidence.

## 3. Localize defects

* Check the network response before concluding the frontend is wrong: a correct response with a wrong UI is a frontend defect, and a wrong response is a backend defect.
* Never resolve a staging finding by weakening a test or asserting behaviour you did not observe.

## 4. Boundaries

* No provider settings, environment variables, infrastructure, or remote database mutations without explicit authorization.
* Do not treat local deterministic provider tests as provider acceptance.

## 5. Report and hand off

* Record the environment, commit, account role, action, observed result, accept/fail outcome, and the unresolved observations the repository still needs to reconcile.
* External verification stays outstanding until the evidence exists. Never relabel it verified.
