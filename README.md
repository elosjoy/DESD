# DESD
Group Project - 06

## Add real data

### Option 1: Use Django admin
1. Run migrations and create an admin user:
	- `& "c:/Github/Uni Work/DESD/.venv/Scripts/python.exe" manage.py migrate`
	- `& "c:/Github/Uni Work/DESD/.venv/Scripts/python.exe" manage.py createsuperuser`
2. Start the app:
	- `& "c:/Github/Uni Work/DESD/.venv/Scripts/python.exe" manage.py runserver`
3. Open `/admin` and add records in this order:
	- Category
	- ProducerProfile
	- Product

### Option 2: Import from CSV (recommended for bulk real data)
1. Copy and edit `real_products_template.csv` with your data.
2. Dry run to validate:
	- `& "c:/Github/Uni Work/DESD/.venv/Scripts/python.exe" manage.py import_real_products real_products_template.csv --dry-run`
3. Run the real import:
	- `& "c:/Github/Uni Work/DESD/.venv/Scripts/python.exe" manage.py import_real_products real_products_template.csv`

CSV columns required:
- `name`
- `price`
- `category_name`
- `category_slug`
- `producer_username`
- `producer_name`
- `contact_name`
- `phone`
- `address`
- `postcode`
- `description`
- `allergen_info`
- `stock_quantity`
- `availability_status` (`AVAILABLE`, `IN_SEASON`, `UNAVAILABLE`, `OUT_OF_SEASON`)
