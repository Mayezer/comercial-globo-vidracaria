# Features and workflows

[Project README](../README.md) · [Documentation index](README.md)

Access roles, customer journeys, business rules, and application routes.

## Overview and access roles

The application combines a public storefront, a customer area, and a management dashboard. Permissions are checked in the views as well as reflected in the menus.

| Role | Available features | Main access control |
| --- | --- | --- |
| Visitor | Home page, contact information, catalog, and details of published products and services. | Public views; only records with `show_in_showcase=True` appear in the catalog. |
| Customer | Individual or business registration, authentication, profile, email verification, quote requests, and deletion of their own account. | Authenticated session linked to a `Profile`. |
| Operations administrator | Management of customers, catalog, quotes, sales, inventory, finances, employees, suppliers, and company settings. | An authenticated, active user with `is_staff=True`. |
| Superuser | Operational features plus creation and editing of other administrator accounts through the dashboard. | `is_superuser=True` in the administrator management views. |

The custom dashboard is available at `/painel/`. Django Admin remains available at `/admin/` for managing registered models according to Django permissions. Accounts created through the dashboard receive operational access without automatically gaining superuser privileges.

**Login accounts and employee records are separate concepts:** `User` identifies who signs in and performs actions; `Employee` stores the personnel and compensation details used for payroll.

## Features and business workflows

### Storefront and catalog

- The home page features up to six published products, with the most recent first.
- Products have a category, photo, description, price, and stock quantity.
- Services have a name, type, description, photo, and publication control.
- Public product and service lists are paginated with six items per page.
- The `show_in_showcase` field controls both listing visibility and public access to detail pages. Hidden records return 404 on these pages.
- Navigation provides contact information, social media links, light/dark themes, and access to quote requests.

The catalog is populated from the database. In a fresh installation, pages may contain no products until the team creates and publishes the first records.

### Registration, authentication, and profiles

1. The visitor provides an account type, CPF/CNPJ, email address, and password. CPF and CNPJ are Brazilian personal and business tax identifiers, respectively.
2. The system validates the document's check digits, normalizes the data, and creates the account and profile.
3. Customers sign in using their **CPF or CNPJ and password**. The login form rejects email addresses as identifiers. Django's default backend also supports administrator accounts using their username.
4. In the profile area, customers can update their personal details, address, phone number, and photo.
5. If email delivery is enabled, registration or a resend request generates a signed verification link valid for 24 hours. The link is tied to the current email address and cannot be reused after verification.
6. Deleting one's own account requires an authenticated POST request. Previously submitted quotes retain copies of the data needed for the operational history.

Email verification has its own state in `email_verified_at`. The quote view checks authentication, address completeness, and the interval between requests; it currently does not require this verification state.

### Quote requests

1. The authenticated customer opens `/orcamento/solicitar/`.
2. If the street, neighborhood, or house number is missing, the system directs the customer to edit their profile.
3. The form lets the customer select published products and services and provide request details.
4. Within a transaction, the application locks the customer record, rechecks the conditions, and saves the quote with a copy of the customer's contact and address details.
5. There is a minimum interval of **four hours per customer** between requests. The server checks the rule again when the form is submitted, even if the page is already open.
6. Customers can see their five most recent requests. The team tracks requests in the dashboard and marks them as pending, completed, or canceled.

Each status change records the responsible administrator and timestamp in `QuoteStatusHistory`. The dashboard checks for new notifications every 15 seconds while the page is visible and records delivery per administrator in `QuoteAdminNotification`. This uses browser polling.

### Sales, line items, and inventory

The sales workflow is **draft → review → completion → cancellation, if needed**. Sales can be associated with a registered customer, an identified walk-in customer, or an anonymous walk-in customer.

| Item type | Input | Calculation and effect |
| --- | --- | --- |
| Product | Product and whole-number quantity. | Quantity × unit price, minus the item discount. Stock is deducted on completion. |
| Glass/material per m² | Material, width and height in millimeters, number of pieces, and price per m². | Total area in m² × unit price, minus the item discount. |
| Service | Service, quantity, and unit price. | Quantity × unit price, minus the item discount. |

Sales calculations are recomputed on the server using `Decimal`:

```text
total area (m²) = width (mm) × height (mm) × pieces ÷ 1,000,000
item total = gross item amount − item discount
sale subtotal = sum of item totals
sale total = subtotal − overall discount
```

On completion, `sales/services.py`:

1. Opens a transaction and locks the sale and the relevant product records.
2. Revalidates the items, stock availability, discounts, and customer data.
3. Requires at least one item, a positive total, a payment method, and a paid amount equal to the total.
4. Creates the cash inflow, deducts product stock, and records the stock movements.
5. Marks the sale as completed and paid.

Cancellation requires a completed sale and a reason. The operation returns products to stock, records the return movements, creates a cash outflow for the refund, and preserves the original records. Repeating completion or cancellation for an already processed sale returns its current state, preventing duplicate effects.

Items in completed or canceled sales are protected against changes through the editing workflow. Records retain snapshots of the commercial information and customer data used for the sale. Automatic stock movements apply to product items.

### Cash management, expenses, and personnel

- **Daily cash management:** inflows, outflows, payment methods, and balances by date.
- **Monthly financial reporting:** consolidated transactions and PDF report export.
- **Expenses:** categorized expenses with an optional supplier and a linked cash outflow.
- **Employees:** identification, photo, and monthly salary.
- **Payroll:** payroll period, gross salary, additions, deductions, payment date, and payment method. Saving payroll synchronizes its cash outflow; quick generation uses the employee's recorded salary.
- **Suppliers:** registration details, contact information, and active status.
- **Settings:** company and finance manager information used in reports.

Net pay is calculated as gross salary + additions − deductions. The code also synchronizes expense and payroll changes and deletions with their corresponding cash entries. Transactions originating from sales have specific protections to preserve their relationship with payment and refund records.

### Calculators

| Tool | Input units | Behavior |
| --- | --- | --- |
| Material per m² | Width and height in meters. | `width × height × price/m²`. |
| Material per linear meter | Length in meters. | `length × price/meter`. |
| Profit calculation | Cost and markup percentage. | `suggested price = cost × (1 + percentage/100)`. |

These simulations run in the browser. The profit calculator's percentage represents **markup on cost**. When selling material per m², dimensions are entered in **millimeters** and the final calculation runs on the server; keep this distinction in mind when using the two screens.

## Main routes

These tables show entry points; the complete creation, editing, and deletion routes are defined in each module's `urls.py` file.

| Path | Purpose | Access |
| --- | --- | --- |
| `/` | Home page. | Public. |
| `/produtos/` and `/produtos/<id>/` | Catalog and details of a published product. | Public. |
| `/servicos/` and `/servicos/<id>/` | Catalog and details of a published service. | Public. |
| `/criar-conta/` and `/entrar/` | Registration and authentication. | Visitor. |
| `/perfil/` and `/perfil/editar/` | Customer profile. | Authenticated customer. |
| `/perfil/reenviar-confirmacao/` | Resend verification through POST. | Authenticated customer. |
| `/confirmar-email/<token>/` | Signed link verification. | Holder of a valid link. |
| `/sair/` and `/excluir-conta/` | Sign out or delete one's own account through POST. | Authenticated user; account deletion is limited to customers. |
| `/orcamento/solicitar/` | Form and recent quote requests. | Authenticated customer; submission requires a complete address. |
| `/sitemap.xml`, `/robots.txt`, `/llms.txt` | Discovery and description of public pages. | Public. |

| Path | Management area | Access |
| --- | --- | --- |
| `/painel/` | Overview. | Active staff. |
| `/painel/administradores/` | Administrator accounts. | Superuser. |
| `/painel/orcamentos/` | Request handling and history. | Active staff. |
| `/painel/notificacoes/proximo-orcamento/` | POST notification polling endpoint. | Active staff. |
| `/painel/clientes/` | Customers and profile editing. | Active staff. |
| `/painel/produtos/` and `/painel/produtos/saidas/` | Catalog and manual stock withdrawals. | Active staff. |
| `/painel/servicos/` | Service records. | Active staff. |
| `/painel/calculadora/` | Materials and measurement-based calculations. | Active staff. |
| `/painel/vendas/` | Sales list and workflow. | Active staff. |
| `/painel/caixa/` | Daily cash entries. | Active staff. |
| `/painel/faturamento/` and `/painel/faturamento/pdf/` | Monthly financial reporting and PDF. | Active staff. |
| `/painel/calculo-de-lucro/` | Cost markup simulation. | Active staff. |
| `/painel/gastos/` | Expenses. | Active staff. |
| `/painel/funcionarios/` | Employee records. | Active staff. |
| `/painel/folhas-de-pagamento/` | Payroll and individual PDFs. | Active staff. |
| `/painel/fornecedores/` | Suppliers. | Active staff. |
| `/painel/configuracoes/` | Company operating details. | Active staff. |
| `/admin/` | Django Admin. | Django administrative permissions. |

The legacy paths `/admin/painel` and `/admin/painel/` redirect to the custom dashboard.
