# Tobias Additions

## Brief rundown of changes

Implemented around test cases **TC-001**, **TC-003**, and **TC-006**. Along with **TC-011**, **TC-014** and **TC-015**

- Added producer web registration flow:
  - `register/producer/` route
  - `ProducerRegistrationForm` in `marketplace/forms.py`
  - `register_producer` view in `marketplace/views.py`
  - `marketplace/templates/marketplace/register_producer.html`
- Added producer product management flow:
  - `producer/products/` dashboard route
  - `producer/products/new/` create-product route
  - `ProducerProductForm` in `marketplace/forms.py`
  - `producer_products` and `producer_product_create` views in `marketplace/views.py`
  - `producer_products.html` and `producer_product_form.html` templates
- Added category bootstrap support:
  - `seed_categories` management command in `marketplace/management/commands/seed_categories.py`
  - producer product create view now warns/redirects if categories are missing
- Added customer cart flow (TC-006 support):
  - session-based cart utility in `marketplace/cart.py`
  - product/cart routes in `marketplace/urls.py`
  - cart/product views in `marketplace/views.py`
  - new templates: `cart.html`, `product_detail.html`
  - updated `home.html` and `category.html` for cart links and add-to-cart actions

## Demo run/test steps

### 1) Start app with Docker
```powershell
Set-Location "c:\Users\Tobey\Desktop\DESD\DESD-1"
docker compose up -d --build
```

### 2) Seed categories (needed for producer product form)
```powershell
docker compose exec web python manage.py seed_categories
```

### 3) (One-time) Create admin user (optional but useful)
```powershell
docker compose exec web python manage.py createsuperuser
```

### 4) TC-001 demo: Producer registration
1. Open `http://localhost:8000/register/producer/`
2. Fill in producer details and submit.
3. Log in at `http://localhost:8000/accounts/login/`.

### 5) TC-003 demo: Producer adds a product
1. Open `http://localhost:8000/producer/products/`.
2. Click **Add New Product**.
3. Fill product details (name, category, price, stock, availability) and save.
4. Confirm product appears in producer list and category browsing.

### 6) TC-006 demo: Customer cart behavior
1. Open `http://localhost:8000/` and browse/search products.
2. Open a product and add quantity to cart.
3. Add a second product.
4. Open `http://localhost:8000/cart/`.
5. Verify both products, quantities, and total.
6. Update one quantity and verify total recalculates.

### 7) Basic check
```powershell
docker compose exec web python manage.py check
```
