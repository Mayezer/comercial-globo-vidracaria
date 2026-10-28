# File reference

[Project README](../README.md) · [Documentation index](README.md)

The responsibility of every distributed file and the handling of local/generated files.

## File-by-file documentation

This inventory covers the **213 source, configuration, documentation, test, and asset files in the public distribution**, including initializers and migrations. Paths are relative to the repository root, and links open the corresponding file. Dependencies, uploads, and generated output are described in the next section without reproducing private data.

The `__init__.py` files listed below are empty and identify Python packages. Some scaffolding files do not yet contain their own behavior; these are identified explicitly to avoid attributing unimplemented features to them.


### Root files and continuous integration

| File | Responsibility |
| --- | --- |
| [`.dockerignore`](../.dockerignore) | Defines which files may enter the Django image build context and excludes secrets and local data. |
| [`.env.example`](../.env.example) | Documents variables and placeholders for generating a local configuration with a demo database. |
| [`.gitignore`](../.gitignore) | Excludes credentials, databases, uploads, backups, dependencies, and generated files from new Git tracking. |
| [`.gitleaks.toml`](../.gitleaks.toml) | Extends the scanner's default rules and limits exceptions to four fictional passwords in specific tests. |
| [`.github/workflows/secret-scanning.yml`](../.github/workflows/secret-scanning.yml) | Checks tracked paths, publication tests, and history with Gitleaks; verifies the downloaded binary's checksum. |
| [`Dockerfile`](../Dockerfile) | Builds the Python environment, installs dependencies, collects static assets, and runs the application as a non-root user. |
| [`docker-compose.yaml`](../docker-compose.yaml) | Provides local PostgreSQL 17 with a persistent volume, health check, required password, and a 127.0.0.1 bind address. |
| [`manage.py`](../manage.py) | Entry point for Django commands: local server, migrations, tests, users, static collection, and custom commands. |
| [`package.json`](../package.json) | Defines Worker dependencies and scripts. The private field prevents accidental npm publication; it does not control GitHub visibility. |
| [`pnpm-lock.yaml`](../pnpm-lock.yaml) | Records JavaScript/TypeScript dependency resolutions for reproducible pnpm installations. |
| [`pnpm-workspace.yaml`](../pnpm-workspace.yaml) | Declares the workspace, approved build scripts, and patched versions of transitive dependencies. |
| [`requirements.txt`](../requirements.txt) | Pins the Python dependencies used by the backend and Docker image. |
| [`tsconfig.json`](../tsconfig.json) | Defines strict TypeScript checking, module resolution, and files included in validation. |
| [`worker-configuration.d.ts`](../worker-configuration.d.ts) | Wrangler-generated environment and Worker binding types; regenerate with cf-typegen. |
| [`wrangler.jsonc`](../wrangler.jsonc) | Configures the domain, Worker, container, Durable Object, R2, rate limits, variables, secret names, and observability. |
| [`README.md`](../README.md) | Repository landing page with a project overview, quick start, and links to detailed documentation. |
| [`PUBLICATION.md`](../PUBLICATION.md) | Guides source review, export, and publication without exposing local data or unaudited history. |
| [`SECURITY.md`](../SECURITY.md) | Defines private vulnerability reporting and links to operational security guidance. |
| [`SECURITY_DEPLOYMENT.md`](../SECURITY_DEPLOYMENT.md) | Details encryption, rotation, backups, migrations, rollback, and external deployment checks. |

### Application core — app/

| File | Responsibility |
| --- | --- |
| [`app/asgi.py`](../app/asgi.py) | Exposes Django's standard ASGI application for compatible servers. |
| [`app/wsgi.py`](../app/wsgi.py) | Exposes the WSGI application used by Gunicorn in the container. |
| [`app/settings.py`](../app/settings.py) | Centralizes database, middleware, template, authentication, storage, email, logging, and production security configuration. |
| [`app/urls.py`](../app/urls.py) | Combines module routes, account routes, Django Admin, SEO endpoints, and legacy redirects. |
| [`app/context_processors.py`](../app/context_processors.py) | Provides templates with the canonical URL, Google verification, and public LocalBusiness metadata. |
| [`app/crypto.py`](../app/crypto.py) | Implements AES-GCM, HMAC indexes, and protected text, email, and decimal ORM fields. |
| [`app/logging.py`](../app/logging.py) | Redacts sensitive patterns and applies this processing to Python log formatting. |
| [`app/middleware.py`](../app/middleware.py) | Adds CSP and other security headers and restricts CORS to authorized public read-only pages. |
| [`app/seo.py`](../app/seo.py) | Generates the sitemap, robots.txt, and llms.txt using URLs and content from published records. |
| [`app/storage.py`](../app/storage.py) | Implements Django's Storage interface through calls to the private media.internal host handled by the Worker and R2. |
| [`app/validators.py`](../app/validators.py) | Validates the extension, actual format, size, dimensions, and integrity of uploaded images. |
| [`app/tests.py`](../app/tests.py) | Checks production headers and the friendly 404 error page. |
| [`app/test_security.py`](../app/test_security.py) | Tests encryption, tampering, rotation, HMAC, CORS, injection inputs, and log redaction. |
| [`app/test_seo.py`](../app/test_seo.py) | Tests public URLs, the sitemap, robots, llms.txt, metadata, and discovery content. |
| [`app/test_settings.py`](../app/test_settings.py) | Checks that production PostgreSQL requires an explicit password and development has no hardcoded password. |

### Accounts and authentication — accounts/

| File | Responsibility |
| --- | --- |
| [`accounts/apps.py`](../accounts/apps.py) | Configures the module and replaces Django Admin's login form with the protected login-attempt version. |
| [`accounts/models.py`](../accounts/models.py) | Defines Profile, protected individual/business data, document validation, search indexes, and AuthenticationThrottle. |
| [`accounts/forms.py`](../accounts/forms.py) | Validates account creation, login, administrator authentication, and profile/address/photo editing. |
| [`accounts/backends.py`](../accounts/backends.py) | Authenticates customers through the document's HMAC index; retains a backend alias for older sessions. |
| [`accounts/security.py`](../accounts/security.py) | Normalizes identifiers and handles failures, progressive lockouts, expiration, and cleanup after successful login. |
| [`accounts/views.py`](../accounts/views.py) | Coordinates registration, login, profiles, email verification/resends, logout, and deletion of one's own account. |
| [`accounts/admin.py`](../accounts/admin.py) | Registers profiles in Django Admin with masked document numbers and exact lookups through protected indexes. |
| [`accounts/tests.py`](../accounts/tests.py) | Tests CPF/CNPJ validation, uploads, account workflows, verification, enumeration protection, and login lockouts. |
| [`accounts/management/commands/rotate_sensitive_data.py`](../accounts/management/commands/rotate_sensitive_data.py) | Counts records to re-encrypt and applies transactional rotation with --apply while retaining the configured old keys. |
| [`accounts/templates/accounts/login.html`](../accounts/templates/accounts/login.html) | Renders the identifier and password login form. |
| [`accounts/templates/accounts/register.html`](../accounts/templates/accounts/register.html) | Renders individual/business registration and adapts document field presentation. |
| [`accounts/templates/accounts/profile.html`](../accounts/templates/accounts/profile.html) | Displays customer data, verification status, and profile/account actions. |
| [`accounts/templates/accounts/profile_edit.html`](../accounts/templates/accounts/profile_edit.html) | Renders editing of personal details, address, contact information, and photo upload. |
| [`accounts/templates/accounts/_delete_account_dialog.html`](../accounts/templates/accounts/_delete_account_dialog.html) | Confirmation component and POST form for deleting one's own account. |
| [`accounts/migrations/0001_initial.py`](../accounts/migrations/0001_initial.py) | Creates the initial profile model linked to the Django user. |
| [`accounts/migrations/0002_profile_email_verified_at.py`](../accounts/migrations/0002_profile_email_verified_at.py) | Adds the email verification timestamp to the profile. |
| [`accounts/migrations/0003_alter_profile_profile_photo.py`](../accounts/migrations/0003_alter_profile_profile_photo.py) | Updates the profile photo field and its validation. |
| [`accounts/migrations/0004_profile_corporate_name_hash_profile_document_hash_and_more.py`](../accounts/migrations/0004_profile_corporate_name_hash_profile_document_hash_and_more.py) | Prepares encrypted fields and HMAC indexes and creates persistent authentication attempt tracking. |
| [`accounts/migrations/0005_encrypt_sensitive_data.py`](../accounts/migrations/0005_encrypt_sensitive_data.py) | Migrates legacy account and related domain data into protected fields and indexes, including opaque customer user identifiers. |
| [`accounts/migrations/0006_require_profile_blind_indexes.py`](../accounts/migrations/0006_require_profile_blind_indexes.py) | Requires unique document and email indexes after data migration. |

### Categories — categories/

| File | Responsibility |
| --- | --- |
| [`categories/apps.py`](../categories/apps.py) | Configures the classification module, displayed as Catálogo in Django Admin. |
| [`categories/models.py`](../categories/models.py) | Defines Category, the classification entity referenced by products. |
| [`categories/admin.py`](../categories/admin.py) | Registers categories in Django Admin with ordering and name-based search. |
| [`categories/views.py`](../categories/views.py) | Scaffolding with no custom views; category management takes place in the admin and products dashboard. |
| [`categories/tests.py`](../categories/tests.py) | Checks that a category's string representation uses its name. |
| [`categories/migrations/0001_initial.py`](../categories/migrations/0001_initial.py) | Creates the initial categories table. |

### Products and inventory — products/

| File | Responsibility |
| --- | --- |
| [`products/apps.py`](../products/apps.py) | Configures the products application. |
| [`products/models.py`](../products/models.py) | Defines products, prices, categories, stock, and publication, plus ProductStockExit with before/after balances and the responsible user. |
| [`products/views.py`](../products/views.py) | Lists published products with pagination and serves public details while respecting the publication setting. |
| [`products/urls.py`](../products/urls.py) | Defines public list and detail routes in the products namespace. |
| [`products/admin.py`](../products/admin.py) | Registers products and stock withdrawals; historical withdrawals cannot be created or deleted manually through this admin. |
| [`products/tests.py`](../products/tests.py) | Tests the model, publication, pagination, public details, and product Django Admin behavior. |
| [`products/templates/products/product_list.html`](../products/templates/products/product_list.html) | Public product catalog page composed of cards and pagination. |
| [`products/templates/products/product_detail.html`](../products/templates/products/product_detail.html) | Detail page for a published product and its commercial information. |
| [`products/templates/products/_product_card.html`](../products/templates/products/_product_card.html) | Product card reused on the home page and product list. |
| [`products/static/products/css/catalog.css`](../products/static/products/css/catalog.css) | Styles for product catalog components and presentation. |
| [`products/migrations/0001_initial.py`](../products/migrations/0001_initial.py) | Creates the initial product model related to its category. |
| [`products/migrations/0002_alter_product_photo.py`](../products/migrations/0002_alter_product_photo.py) | Updates the product image field and upload validation. |
| [`products/migrations/0003_product_show_in_showcase.py`](../products/migrations/0003_product_show_in_showcase.py) | Adds the product's public visibility control. |
| [`products/migrations/0004_product_stock_quantity_productstockexit.py`](../products/migrations/0004_product_stock_quantity_productstockexit.py) | Adds stock quantities and withdrawal history with balances and authorship. |

### Glazing services — glazing_services/

| File | Responsibility |
| --- | --- |
| [`glazing_services/apps.py`](../glazing_services/apps.py) | Configures the current package and retains the historical services label for table and migration compatibility. |
| [`glazing_services/models.py`](../glazing_services/models.py) | Defines Service with a type, description, photo, and storefront publication control. |
| [`glazing_services/views.py`](../glazing_services/views.py) | Lists published services and serves public details with pagination and protection for hidden records. |
| [`glazing_services/urls.py`](../glazing_services/urls.py) | Defines public routes in the glazing_services namespace. |
| [`glazing_services/admin.py`](../glazing_services/admin.py) | Registers services, filters, and presentation editing in Django Admin. |
| [`glazing_services/tests.py`](../glazing_services/tests.py) | Tests rename compatibility, the model, public catalog, and administrative integration. |
| [`glazing_services/templates/glazing_services/service_list.html`](../glazing_services/templates/glazing_services/service_list.html) | Public service catalog with cards and pagination. |
| [`glazing_services/templates/glazing_services/service_detail.html`](../glazing_services/templates/glazing_services/service_detail.html) | Detailed presentation of a published service. |
| [`glazing_services/templates/glazing_services/_service_card.html`](../glazing_services/templates/glazing_services/_service_card.html) | Reusable service card for the list. |
| [`glazing_services/migrations/0001_initial.py`](../glazing_services/migrations/0001_initial.py) | Creates the Service model using the historical application label. |
| [`glazing_services/migrations/0002_alter_service_photo.py`](../glazing_services/migrations/0002_alter_service_photo.py) | Updates the service photo field and its upload validation. |
| [`glazing_services/migrations/0003_service_show_in_showcase.py`](../glazing_services/migrations/0003_service_show_in_showcase.py) | Adds the option to publish a service in the storefront. |

### Storefront — showcase/

| File | Responsibility |
| --- | --- |
| [`showcase/apps.py`](../showcase/apps.py) | Configures the public presentation module. |
| [`showcase/models.py`](../showcase/models.py) | Scaffolding with no custom models; the storefront queries products and services from their own modules. |
| [`showcase/admin.py`](../showcase/admin.py) | Scaffolding with no custom administrative registrations. |
| [`showcase/views.py`](../showcase/views.py) | Selects up to six of the most recently published products and renders the home page. |
| [`showcase/tests.py`](../showcase/tests.py) | Tests storefront routes, home page structure, presentation, and related navigation. |
| [`showcase/templates/showcase/base.html`](../showcase/templates/showcase/base.html) | Independent public layout with SEO metadata, Bootstrap, themes, navigation, contact information, and footer. |
| [`showcase/templates/showcase/home.html`](../showcase/templates/showcase/home.html) | Company home page with a cover, introduction, and featured products. |
| [`showcase/templates/showcase/_pagination.html`](../showcase/templates/showcase/_pagination.html) | Pagination component for public catalogs. |
| [`showcase/static/img/foto_capa_globo_vidracaria.jpg`](../showcase/static/img/foto_capa_globo_vidracaria.jpg) | Photograph used as the storefront cover image. |
| [`showcase/static/img/logo_globo.jpeg`](../showcase/static/img/logo_globo.jpeg) | Visual identity used in navigation, the favicon, and sharing metadata. |

### Material calculator — calculator/

| File | Responsibility |
| --- | --- |
| [`calculator/apps.py`](../calculator/apps.py) | Configures the materials and calculator application. |
| [`calculator/models.py`](../calculator/models.py) | Defines Material with a unique name, m² or linear-meter unit, and unit price. |
| [`calculator/forms.py`](../calculator/forms.py) | Validates material records and the unit price submitted in the form. |
| [`calculator/views.py`](../calculator/views.py) | Serves the calculator and controls staff creation, editing, and deletion of materials. |
| [`calculator/urls.py`](../calculator/urls.py) | Groups calculator and material maintenance routes. |
| [`calculator/admin.py`](../calculator/admin.py) | Registers materials in Django Admin with search and unit filters. |
| [`calculator/tests.py`](../calculator/tests.py) | Tests the model, permissions, and calculator maintenance/usage workflow. |
| [`calculator/templates/calculator/calculator.html`](../calculator/templates/calculator/calculator.html) | Interface and JavaScript for material selection, search, and m² or linear-meter simulations. |
| [`calculator/templates/calculator/material_form.html`](../calculator/templates/calculator/material_form.html) | Form for creating or editing a material's name, unit, and price. |
| [`calculator/migrations/0001_initial.py`](../calculator/migrations/0001_initial.py) | Creates the materials table and its unit/price structure. |

### Management dashboard — dashboard/

| File | Responsibility |
| --- | --- |
| [`dashboard/apps.py`](../dashboard/apps.py) | Configures the custom management dashboard module. |
| [`dashboard/models.py`](../dashboard/models.py) | Defines quotes, history, notifications, cash entries, employees, suppliers, expenses, payroll, and company settings. |
| [`dashboard/forms.py`](../dashboard/forms.py) | Validates dashboard operations, Brazilian-format monetary fields, customers, catalog records, personnel, expenses, and administrator accounts. |
| [`dashboard/decorators.py`](../dashboard/decorators.py) | Implements staff_required and superuser_required checks for protected views. |
| [`dashboard/views.py`](../dashboard/views.py) | Coordinates management screens, quote requests, filters, manual stock withdrawals, cash synchronization, and reports. |
| [`dashboard/urls.py`](../dashboard/urls.py) | Maps dashboard routes, quote submission, notifications, and PDFs. |
| [`dashboard/admin.py`](../dashboard/admin.py) | Registers financial and personnel models in Django Admin, with specific protections for sale-linked cash entries. |
| [`dashboard/pdf.py`](../dashboard/pdf.py) | Builds text-based PDF documents with page organization and escaping of report text. |
| [`dashboard/tests.py`](../dashboard/tests.py) | Exercises management workflows, authorization, quotes, catalog, cash management, personnel, expenses, and reports. |
| [`dashboard/templates/dashboard/base.html`](../dashboard/templates/dashboard/base.html) | Extends the general layout with a sidebar, groups, administrative components, and notification polling. |
| [`dashboard/templates/dashboard/home.html`](../dashboard/templates/dashboard/home.html) | Dashboard overview with indicators and recent requests. |
| [`dashboard/templates/dashboard/administrator_list.html`](../dashboard/templates/dashboard/administrator_list.html) | Lists administrator accounts for the superuser. |
| [`dashboard/templates/dashboard/administrator_form.html`](../dashboard/templates/dashboard/administrator_form.html) | Creates/edits administrators, including passwords and active status where applicable. |
| [`dashboard/templates/dashboard/quote_list.html`](../dashboard/templates/dashboard/quote_list.html) | Screen for searching and filtering incoming quote requests. |
| [`dashboard/templates/dashboard/_quote_table.html`](../dashboard/templates/dashboard/_quote_table.html) | Quote table reused in the list and dashboard overview. |
| [`dashboard/templates/dashboard/quote_detail.html`](../dashboard/templates/dashboard/quote_detail.html) | Request details, preserved customer information, contact details, and handling history/status. |
| [`dashboard/templates/dashboard/request_quote.html`](../dashboard/templates/dashboard/request_quote.html) | Customer form, waiting-interval countdown, and recent request tracking. |
| [`dashboard/templates/dashboard/customer_list.html`](../dashboard/templates/dashboard/customer_list.html) | Search and paginated list of customer profiles. |
| [`dashboard/templates/dashboard/customer_form.html`](../dashboard/templates/dashboard/customer_form.html) | Administrative editing of customer details and account active status. |
| [`dashboard/templates/dashboard/product_list.html`](../dashboard/templates/dashboard/product_list.html) | Management of catalog products and categories. |
| [`dashboard/templates/dashboard/product_form.html`](../dashboard/templates/dashboard/product_form.html) | Creates/edits products, categories, prices, stock, photos, and publication settings. |
| [`dashboard/templates/dashboard/product_stock_exit.html`](../dashboard/templates/dashboard/product_stock_exit.html) | Manual withdrawal form and stock movement history. |
| [`dashboard/templates/dashboard/service_list.html`](../dashboard/templates/dashboard/service_list.html) | Management list of glazing services. |
| [`dashboard/templates/dashboard/service_form.html`](../dashboard/templates/dashboard/service_form.html) | Creates/edits a service's type, description, photo, and publication setting. |
| [`dashboard/templates/dashboard/cash_daily.html`](../dashboard/templates/dashboard/cash_daily.html) | Daily cash view with inflows, outflows, and balance. |
| [`dashboard/templates/dashboard/cash_transaction_form.html`](../dashboard/templates/dashboard/cash_transaction_form.html) | Creates/edits a manual cash entry. |
| [`dashboard/templates/dashboard/monthly_finance.html`](../dashboard/templates/dashboard/monthly_finance.html) | Monthly transaction summary and PDF report access. |
| [`dashboard/templates/dashboard/profit_calculator.html`](../dashboard/templates/dashboard/profit_calculator.html) | Browser simulation of price and profit from cost and a markup percentage. |
| [`dashboard/templates/dashboard/expense_list.html`](../dashboard/templates/dashboard/expense_list.html) | Expense queries by month/category and their totals. |
| [`dashboard/templates/dashboard/expense_form.html`](../dashboard/templates/dashboard/expense_form.html) | Creates/edits an expense, payment details, and an optional supplier link. |
| [`dashboard/templates/dashboard/employee_list.html`](../dashboard/templates/dashboard/employee_list.html) | Employee records and compensation information. |
| [`dashboard/templates/dashboard/employee_form.html`](../dashboard/templates/dashboard/employee_form.html) | Creates/edits employees, CPF, photo, and monthly salary. |
| [`dashboard/templates/dashboard/payroll_list.html`](../dashboard/templates/dashboard/payroll_list.html) | Payroll queries by period and generation/PDF actions. |
| [`dashboard/templates/dashboard/payroll_form.html`](../dashboard/templates/dashboard/payroll_form.html) | Creates/edits gross salary, additions, deductions, and payment details. |
| [`dashboard/templates/dashboard/supplier_list.html`](../dashboard/templates/dashboard/supplier_list.html) | Queries and maintains registered suppliers. |
| [`dashboard/templates/dashboard/supplier_form.html`](../dashboard/templates/dashboard/supplier_form.html) | Form for supplier identification, contact information, address, and active status. |
| [`dashboard/templates/dashboard/system_settings.html`](../dashboard/templates/dashboard/system_settings.html) | Edits company and finance manager details used by the system. |
| [`dashboard/templates/dashboard/_pagination.html`](../dashboard/templates/dashboard/_pagination.html) | Pagination component for administrative queries that include it. |
| [`dashboard/migrations/0001_initial.py`](../dashboard/migrations/0001_initial.py) | Creates quote requests, status history, and per-administrator notification tracking. |
| [`dashboard/migrations/0002_employee_cashtransaction.py`](../dashboard/migrations/0002_employee_cashtransaction.py) | Adds employees and cash entries to the management domain. |
| [`dashboard/migrations/0003_supplier_systemsettings_payroll_expense.py`](../dashboard/migrations/0003_supplier_systemsettings_payroll_expense.py) | Adds suppliers, company settings, payroll, and expenses. |
| [`dashboard/migrations/0004_alter_employee_options_alter_payroll_options_and_more.py`](../dashboard/migrations/0004_alter_employee_options_alter_payroll_options_and_more.py) | Prepares protected fields and HMAC indexes in management models and updates ordering options. |
| [`dashboard/migrations/0005_require_employee_cpf_blind_index.py`](../dashboard/migrations/0005_require_employee_cpf_blind_index.py) | Requires a unique protected CPF index for employees. |
| [`dashboard/migrations/0006_encrypt_cash_transaction_amount.py`](../dashboard/migrations/0006_encrypt_cash_transaction_amount.py) | Converts cash amounts to an encrypted decimal field and migrates existing records, removing the incompatible numeric constraint. |

### Sales — sales/

| File | Responsibility |
| --- | --- |
| [`sales/apps.py`](../sales/apps.py) | Configures the sales application. |
| [`sales/models.py`](../sales/models.py) | Defines sales, items, states, historical snapshots, monetary calculations, material area, and stock movements. |
| [`sales/forms.py`](../sales/forms.py) | Validates customers, discounts, payment, product/material/service items, and cancellation reasons. |
| [`sales/services.py`](../sales/services.py) | Performs transactional completion and cancellation, locks records, and synchronizes stock, payment, and refunds. |
| [`sales/views.py`](../sales/views.py) | Coordinates sales listing, creation, editing, item removal, review, completion, details, and cancellation. |
| [`sales/urls.py`](../sales/urls.py) | Defines sales handling and state-transition routes. |
| [`sales/admin.py`](../sales/admin.py) | Presents sales and movements in Django Admin, restricting operations that would bypass the business workflow. |
| [`sales/tests.py`](../sales/tests.py) | Tests sales, validation, calculations, stock, completion, idempotency, and cancellation with refunds. |
| [`sales/templates/sales/sale_list.html`](../sales/templates/sales/sale_list.html) | Sales queries and commercial tracking filters. |
| [`sales/templates/sales/sale_create.html`](../sales/templates/sales/sale_create.html) | Draft creation with customer and sale details. |
| [`sales/templates/sales/sale_edit.html`](../sales/templates/sales/sale_edit.html) | Draft editing and item addition/removal before completion. |
| [`sales/templates/sales/sale_review.html`](../sales/templates/sales/sale_review.html) | Data and amount review before completing the sale. |
| [`sales/templates/sales/sale_detail.html`](../sales/templates/sales/sale_detail.html) | Displays recorded information, status, and available actions for the sale. |
| [`sales/templates/sales/sale_cancel.html`](../sales/templates/sales/sale_cancel.html) | Cancellation confirmation and reason collection. |
| [`sales/templates/sales/_sale_form.html`](../sales/templates/sales/_sale_form.html) | Shared fields of the main sales form. |
| [`sales/templates/sales/_form_field.html`](../sales/templates/sales/_form_field.html) | Consistent rendering of fields, help text, and errors in sales forms. |
| [`sales/templates/sales/_sale_snapshot.html`](../sales/templates/sales/_sale_snapshot.html) | Reusable customer, item, and amount summary for review and detail pages. |
| [`sales/templates/sales/_customer_script.html`](../sales/templates/sales/_customer_script.html) | JavaScript that adapts customer data presentation based on customer type and selection. |
| [`sales/migrations/0001_initial.py`](../sales/migrations/0001_initial.py) | Creates sales, items, and stock movements with their initial relationships and constraints. |
| [`sales/migrations/0002_sale_stock_balance_constraint.py`](../sales/migrations/0002_sale_stock_balance_constraint.py) | Adds a consistency constraint between movement type, quantity, and stock balances. |
| [`sales/migrations/0003_sale_customer_contact_hash_and_more.py`](../sales/migrations/0003_sale_customer_contact_hash_and_more.py) | Prepares customer data, notes, and cancellation details as protected fields and adds HMAC search indexes. |

### Global layouts and styles

| File | Responsibility |
| --- | --- |
| [`templates/base.html`](../templates/base.html) | General account layout and dashboard base, with styles, navigation, messages, themes, and extension blocks. |
| [`templates/404.html`](../templates/404.html) | Resource-not-found page with recovery navigation for users. |
| [`templates/admin/base_site.html`](../templates/admin/base_site.html) | Customizes Django Admin's appearance and branding. |
| [`templates/seo/sitemap.xml`](../templates/seo/sitemap.xml) | XML template used to serialize public sitemap URLs. |
| [`static/css/admin_vidracaria.css`](../static/css/admin_vidracaria.css) | Django Admin customization styles. |
| [`static/css/error-pages.css`](../static/css/error-pages.css) | Error page presentation styles. |

### Worker and container startup

| File | Responsibility |
| --- | --- |
| [`src/index.ts`](../src/index.ts) | Defines DjangoContainer, injects its environment, forwards requests, validates media paths, and integrates the R2 bucket with the private host. |
| [`src/rate-limit.ts`](../src/rate-limit.ts) | Applies per-IP/route limiters to authentication, registration, and verification-resend POST requests. |
| [`src/logging.ts`](../src/logging.ts) | Sanitizes Worker error messages, removing tokens and credential patterns before logging. |
| [`src/rate-limit.test.ts`](../src/rate-limit.test.ts) | Tests limits, separation between routes/IPs, unrestricted paths, and error sanitization. |
| [`docker/entrypoint.sh`](../docker/entrypoint.sh) | Applies migrations when the container starts and replaces the process with Gunicorn on port 8080. |

### Environment and publication tools — scripts/

| File | Responsibility |
| --- | --- |
| [`scripts/create_local_env.py`](../scripts/create_local_env.py) | Generates a local .env with independent keys and restricted Unix access, refusing overwrites. |
| [`scripts/export_public_source.py`](../scripts/export_public_source.py) | Exports a ZIP containing approved source files, documentation, and public images, excluding Git history, data, dependencies, and symbolic links. |
| [`scripts/check_public_files.py`](../scripts/check_public_files.py) | Inspects Git-tracked paths and fails on databases, uploads, named secret files, or prohibited generated files. |
| [`scripts/test_publication.py`](../scripts/test_publication.py) | Tests independent keys, overwrite prevention, data filters, sitemap preservation, and symbolic-link rejection. |

### Python package initializers

| File | Responsibility |
| --- | --- |
| [`accounts/__init__.py`](../accounts/__init__.py) | Identifies accounts as a Python package; contains no application logic. |
| [`accounts/management/__init__.py`](../accounts/management/__init__.py) | Identifies the accounts application's management tools package. |
| [`accounts/management/commands/__init__.py`](../accounts/management/commands/__init__.py) | Identifies the package for custom Django management commands. |
| [`accounts/migrations/__init__.py`](../accounts/migrations/__init__.py) | Identifies the module's migrations package; contains no migration operations. |
| [`app/__init__.py`](../app/__init__.py) | Identifies app as a Python package; contains no application logic. |
| [`calculator/__init__.py`](../calculator/__init__.py) | Identifies calculator as a Python package; contains no application logic. |
| [`calculator/migrations/__init__.py`](../calculator/migrations/__init__.py) | Identifies the module's migrations package; contains no migration operations. |
| [`categories/__init__.py`](../categories/__init__.py) | Identifies categories as a Python package; contains no application logic. |
| [`categories/migrations/__init__.py`](../categories/migrations/__init__.py) | Identifies the module's migrations package; contains no migration operations. |
| [`dashboard/__init__.py`](../dashboard/__init__.py) | Identifies dashboard as a Python package; contains no application logic. |
| [`dashboard/migrations/__init__.py`](../dashboard/migrations/__init__.py) | Identifies the module's migrations package; contains no migration operations. |
| [`glazing_services/__init__.py`](../glazing_services/__init__.py) | Identifies glazing_services as a Python package; contains no application logic. |
| [`glazing_services/migrations/__init__.py`](../glazing_services/migrations/__init__.py) | Identifies the module's migrations package; contains no migration operations. |
| [`products/__init__.py`](../products/__init__.py) | Identifies products as a Python package; contains no application logic. |
| [`products/migrations/__init__.py`](../products/migrations/__init__.py) | Identifies the module's migrations package; contains no migration operations. |
| [`sales/__init__.py`](../sales/__init__.py) | Identifies sales as a Python package; contains no application logic. |
| [`sales/migrations/__init__.py`](../sales/migrations/__init__.py) | Identifies the module's migrations package; contains no migration operations. |
| [`showcase/__init__.py`](../showcase/__init__.py) | Identifies showcase as a Python package; contains no application logic. |
| [`showcase/migrations/__init__.py`](../showcase/migrations/__init__.py) | Identifies the module's migrations package; contains no migration operations. |

### Documentation guides

| File | Responsibility |
| --- | --- |
| [`docs/README.md`](README.md) | Documentation index with task-based reading paths. |
| [`docs/FEATURES.md`](FEATURES.md) | Access roles, customer journeys, business rules, and application routes. |
| [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | System design, module boundaries, data relationships, and the technology stack. |
| [`docs/DEVELOPMENT.md`](DEVELOPMENT.md) | Local setup, Windows instructions, testing, maintenance, and troubleshooting. |
| [`docs/CONFIGURATION.md`](CONFIGURATION.md) | Environment variables for Django, databases, encryption, email, and media. |
| [`docs/SECURITY_GUIDE.md`](SECURITY_GUIDE.md) | Implemented safeguards, data handling, and the boundaries of each control. |
| [`docs/DEPLOYMENT.md`](DEPLOYMENT.md) | Cloudflare configuration, external services, provider secrets, and deployment checks. |
| [`docs/FILE_GUIDE.md`](FILE_GUIDE.md) | The responsibility of every distributed file and the handling of local/generated files. |

## Local and generated files

These paths may exist in the working environment. Their purpose is documented by category because they include third-party dependencies, reproducible output, or private data and are not part of the public source inventory.

| Path | Purpose and handling |
| --- | --- |
| `.env` | Generated local secrets and configuration. Do not commit it or include it in the image. |
| `demo.sqlite3` | New demo database. Do not distribute it with personal records. |
| `db.sqlite3` and other local databases | Existing working databases. Keep them locally and exclude them from publication. |
| `media/` | Uploads, such as product, customer, or employee photos. Do not copy company data into the public repository. |
| `staticfiles/` | Output from collectstatic, including files processed by WhiteNoise. Regenerate it in the target environment. |
| `.venv/` and `venv/` | Python environments with installed dependencies. Recreate them from requirements.txt. |
| `node_modules/` | Worker dependencies installed by pnpm. Recreate them using the lockfile. |
| `__pycache__/` and `.pyc` files | Python compilation cache. Reproducible and excluded from distribution. |
| `tmp/`, logs, and local screenshots | Development and diagnostic output that may contain session or screen data. |
| `dist/` | ZIP archives produced by the exporter. Each package represents the files present when it was generated. |
| `.wrangler/` | Local development state for Cloudflare tooling. |
| `.git/` | Git metadata and history. The original history requires its own review before its visibility changes. |
| `.aws/`, `.codex/`, `.agents/`, and similar local settings | Tool/environment configuration; excluded from the public distribution. |

The export script includes only the two layout images declared in `PUBLIC_IMAGES`. When adding legitimate website assets, deliberately update this list and the documentation. Files inside third-party dependencies follow their respective packages' documentation and licenses.
