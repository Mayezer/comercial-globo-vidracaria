# Security implementation

[Project README](../README.md) · [Documentation index](README.md)

Implemented safeguards, data handling, and the boundaries of each control.

## Security and data handling

| Implemented control | Scope |
| --- | --- |
| Sessions, password hashing, form validation, and CSRF | Authentication and data changes in Django. |
| Staff and superuser checks | Decorators applied to management views. |
| AES-256-GCM with per-field context and a random nonce | Personal data and financial fields protected by custom ORM fields. |
| Independent HMAC indexes | Exact lookups and uniqueness checks for encrypted data; these indexes do not support partial-text searches. |
| Persistent lockout by identifier | Login failures, with customer/admin scopes and progressively increasing delays. |
| Per-IP and per-route Worker limits | 20 POSTs/minute for login/registration/admin and 3 POSTs/minute for verification resends, as configured in `wrangler.jsonc`. |
| Transactions and row-level locking | Sale completion/cancellation, inventory, and quote-request intervals. |
| Upload validation | JPG, PNG, and WEBP, up to 5 MB, with content validation and dimension/pixel limits. |
| Protective headers and restricted CORS | Django responses and Worker media delivery. |
| Log redaction | Removal of sensitive patterns before messages and errors are logged. |
| Git/Docker exclusions and Gitleaks | Protection of source distribution and the image build context. |

Encryption applies to the fields explicitly configured for it. Media files and some operational amounts use the specific controls described in [SECURITY_DEPLOYMENT.md](../SECURITY_DEPLOYMENT.md). The current CSP allows inline scripts and styles to accommodate the existing templates. `robots.txt` guides indexing; views and authentication enforce access control.

The Worker serves objects under `/media/` through valid URLs without checking the customer's Django session. Consider this behavior when deciding which images may be stored and displayed through that path.

The security workflow checks tracked files and the history available in the checkout. It does not replace personal-data review, provider access controls, or an audit of the deployed environment. Follow [SECURITY.md](../SECURITY.md) to report vulnerabilities.
