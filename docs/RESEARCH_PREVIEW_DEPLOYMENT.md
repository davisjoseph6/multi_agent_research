# Public reviewer preview — NOT the participant RCT server

The repository's `docs/index.html` is a standalone **read-only scripted illustration**. It has no API calls, no enrollment, no response persistence, no POMCP execution, no measured learning outcome and no participant data. Its source must not be conflated with the Flask RCT application.

## Publishing with GitHub Pages (requires repository-owner action)

1. Verify the content and any licensing/organizational policy for posting this page publicly.
2. In GitHub repository **Settings > Pages**, select **Deploy from a branch**, choose the intended branch and `/docs` folder; GitHub Pages only supports a root or `/docs` branch folder. Your institution may instead require a controlled internal site. Merge to the default branch if your Pages configuration publishes only from that branch.
3. Wait for GitHub to show the actual Pages deployment URL and verify HTTPS, mobile layout and accessibility. Do not infer a live URL from the repository name before deployment succeeds.
4. Test from a second browser that the preview works without invitation codes, cookies, accounts or API access. Confirm that it cannot enroll or submit a response.
5. Never point a public demo link to the localhost Flask server, expose study databases or publish private invitation tokens.

GitHub Pages is **not** intended to host the private study backend or confidential participant data. The `noindex` tag is not a security control.

## Actual human RCT production deployment

The separate release-gated Flask app requires an institution-approved host, DNS, valid TLS, independent application security testing, legal/privacy approval and completion of the genuine content and measurement review. Review `agent2_realdata_benchmark/ops/rct/README_PRODUCTION_HARDENING.md`. Do not bypass its mechanical live-enrollment gate or use the static preview as a substitute for an approved study deployment.
